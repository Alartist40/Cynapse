use std::{fs, process};
use ed25519_dalek::{Keypair, PublicKey, SecretKey, Signature, Signer, Verifier};
use rand_core::OsRng;

const FOOTER_LEN: usize = 256;
const MAGIC: u32 = 0x53494721;

// Define a type alias for the footer buffer
type Footer = [u8; FOOTER_LEN];

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 { usage(); }
    match args[1].as_str() {
        "--gen-key" => gen_keypair(),
        "sign" => sign(args),
        "verify" => verify(args),
        _ => usage(),
    }
}

fn usage() {
    eprintln!("Usage:\n  sign-model --gen-key\n  sign-model sign <file> [--key keypair.pem]\n  sign-model verify <file> [--key pub.pem]");
    process::exit(1);
}

fn gen_keypair() {
    let keypair = Keypair::generate(&mut OsRng);
    let mut out = Vec::with_capacity(64);
    out.extend_from_slice(keypair.secret.as_bytes());
    out.extend_from_slice(keypair.public.as_bytes());
    fs::write("keypair.pem", out).expect("write");
    println!("[+] keypair.pem created (keep secret)");
}

fn load_keypair(path: &str) -> Keypair {
    let buf = fs::read(path).expect("read key");
    if buf.len() != 64 { panic!("Bad keypair file"); }
    let secret = SecretKey::from_bytes(&buf[..32].try_into().unwrap()).unwrap();
    let public = PublicKey::from_bytes(&buf[32..64].try_into().unwrap()).unwrap();
    Keypair { secret, public }
}

fn load_public(path: &str) -> PublicKey {
    let buf = fs::read(path).expect("read pub");
    if buf.len() == 64 { PublicKey::from_bytes(&buf[32..64].try_into().unwrap()).unwrap() }
    else if buf.len() == 32 { PublicKey::from_bytes(&buf[..32].try_into().unwrap()).unwrap() }
    else { panic!("Bad pub file"); }
}

fn sign(args: Vec<String>) {
    if args.len() < 3 { usage(); }
    let file = &args[2];
    let keypath = args.iter().position(|a| a == "--key").map(|i| &args[i + 1]).unwrap_or(&String::from("keypair.pem"));
    let kp = load_keypair(keypath);
    let mut data = fs::read(file).expect("read model");
    let hash = blake3::hash(&data);
    let sig = kp.sign(hash.as_bytes());
    let mut footer = Footer::default();
    footer[0..64].copy_from_slice(sig.to_bytes().as_slice());
    footer[64..96].copy_from_slice(kp.public.as_bytes());
    footer[96..100].copy_from_slice(&MAGIC.to_le_bytes());
    data.extend_from_slice(&footer);
    let out = format!("{}.signed", file);
    fs::write(&out, data).expect("write signed");
    println!("[+] signed -> {}", out);
}

fn verify(args: Vec<String>) {
    if args.len() < 3 { usage(); }
    let file = &args[2];
    let pubpath = args.iter().position(|a| a == "--key").map(|i| &args[i + 1]).unwrap_or(&String::from("keypair.pem"));
    let pub_key = load_public(pubpath);
    let data = fs::read(file).expect("read signed model");
    if data.len() < FOOTER_LEN { eprintln!("[-] file too small"); process::exit(1); }
    let footer_bytes = &data[data.len() - FOOTER_LEN..];
    let mut footer = Footer::default();
    footer.copy_from_slice(footer_bytes);
    if u32::from_le_bytes(footer[96..100].try_into().unwrap()) != MAGIC {
        eprintln!("[-] Magic mismatch – file not signed"); process::exit(1);
    }
    let sig = Signature::from_bytes(&footer[0..64].try_into().unwrap()).unwrap();
    let sig_pub = PublicKey::from_bytes(&footer[64..96].try_into().unwrap()).unwrap();
    if sig_pub != pub_key { eprintln!("[-] Public key mismatch"); process::exit(1); }
    let model = &data[..data.len() - FOOTER_LEN];
    let hash = blake3::hash(model);
    match pub_key.verify(hash.as_bytes(), &sig) {
        Ok(_) => { println!("[+] Signature valid – model untampered"); process::exit(0); }
        Err(_) => { eprintln!("[-] Signature invalid – TAMPERED"); process::exit(1); }
    }
}
