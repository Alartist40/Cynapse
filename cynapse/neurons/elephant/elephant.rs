// src/lib.rs - Core signing library
use ed25519_dalek::{SigningKey, VerifyingKey, Signature, Signer, Verifier};
use blake3::Hasher;
use rand::rngs::OsRng;
use std::path::Path;
use thiserror::Error;

pub const FOOTER_SIZE: usize = 256;
pub const MAGIC: &[u8; 4] = b"SIG!";

#[derive(Error, Debug)]
pub enum SignError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Invalid key length")]
    InvalidKey,
}

#[derive(Debug, Clone)]
pub struct SignedFile {
    pub content: Vec<u8>,
    pub signature: [u8; 64],
    pub public_key: [u8; 32],
}

impl SignedFile {
    /// Create new signed file from content
    pub fn sign(content: &[u8], signing_key: &SigningKey) -> Self {
        let mut hasher = Hasher::new();
        hasher.update(content);
        let hash = hasher.finalize();
        
        let signature = signing_key.sign(&hash.as_bytes());
        let public_key = signing_key.verifying_key().to_bytes();
        
        Self {
            content: content.to_vec(),
            signature: signature.to_bytes(),
            public_key,
        }
    }
    
    /// Serialize to bytes with footer
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut output = self.content.clone();
        
        // Footer: [64 sig][32 key][4 magic][156 padding]
        output.extend_from_slice(&self.signature);
        output.extend_from_slice(&self.public_key);
        output.extend_from_slice(MAGIC);
        output.extend(vec![0u8; 156]);
        
        output
    }
    
    /// Parse signed file from bytes
    pub fn from_bytes(data: &[u8]) -> Option<Self> {
        if data.len() < FOOTER_SIZE {
            return None;
        }
        
        let content_len = data.len() - FOOTER_SIZE;
        let content = data[..content_len].to_vec();
        
        let footer = &data[content_len..];
        
        // Check magic
        if &footer[96..100] != MAGIC {
            return None;
        }
        
        let mut signature = [0u8; 64];
        signature.copy_from_slice(&footer[0..64]);
        
        let mut public_key = [0u8; 32];
        public_key.copy_from_slice(&footer[64..96]);
        
        Some(Self {
            content,
            signature,
            public_key,
        })
    }
    
    /// Verify signature against content
    pub fn verify(&self) -> Result<bool, SignError> {
        let public_key = VerifyingKey::from_bytes(&self.public_key)
            .map_err(|_| SignError::InvalidKey)?;
        
        let mut hasher = Hasher::new();
        hasher.update(&self.content);
        let hash = hasher.finalize();
        
        let signature = Signature::from_bytes(&self.signature);
        
        match public_key.verify(&hash.as_bytes(), &signature) {
            Ok(_) => Ok(true),
            Err(_) => Ok(false),
        }
    }
    
    /// Quick check if file appears signed (has magic footer)
    pub fn is_signed(data: &[u8]) -> bool {
        if data.len() < FOOTER_SIZE {
            return false;
        }
        &data[data.len()-160..data.len()-156] == MAGIC
    }
}

// Python bindings
use pyo3::prelude::*;

#[pyfunction]
fn sign_file(path: &str, key_path: &str) -> PyResult<String> {
    let content = std::fs::read(path)?;
    let key_bytes = std::fs::read(key_path)?;
    
    let signing_key = SigningKey::from_bytes(
        &key_bytes[..32].try_into()
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid key"))?
    );
    
    let signed = SignedFile::sign(&content, &signing_key);
    let output_path = format!("{}.signed", path);
    std::fs::write(&output_path, signed.to_bytes())?;
    
    Ok(output_path)
}

#[pyfunction]
fn verify_file(path: &str) -> PyResult<bool> {
    let data = std::fs::read(path)?;
    
    let signed = SignedFile::from_bytes(&data)
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Not a signed file"))?;
    
    signed.verify()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
fn is_signed_file(path: &str) -> PyResult<bool> {
    let data = std::fs::read(path)?;
    Ok(SignedFile::is_signed(&data))
}

#[pyfunction]
fn generate_keypair() -> PyResult<(String, String)> {
    let mut csprng = OsRng;
    let signing_key = SigningKey::generate(&mut csprng);
    
    let private_path = "elephant_private.key";
    let public_path = "elephant_public.key";
    
    std::fs::write(private_path, signing_key.as_bytes())?;
    std::fs::write(public_path, signing_key.verifying_key().as_bytes())?;
    
    Ok((private_path.to_string(), public_path.to_string()))
}

#[pymodule]
fn elephant_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sign_file, m)?)?;
    m.add_function(wrap_pyfunction!(verify_file, m)?)?;
    m.add_function(wrap_pyfunction!(is_signed_file, m)?)?;
    m.add_function(wrap_pyfunction!(generate_keypair, m)?)?;
    Ok(())
}