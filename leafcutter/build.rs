use std::path::{Path, PathBuf};

fn main() {
    #[cfg(feature = "llama-ffi")]
    {
        link_llama_cpp();
    }
}

#[cfg(feature = "llama-ffi")]
fn link_llama_cpp() {
    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());

    let llama_build = std::env::var("LLAMA_CPP_BUILD")
        .unwrap_or_else(|_| {
            let vendored = manifest_dir.join("llama.cpp/build");
            if vendored.exists() {
                return vendored.to_string_lossy().to_string();
            }
            let ollama_lib = Path::new("/usr/local/lib/ollama");
            if ollama_lib.join("libllama.so").exists() {
                return ollama_lib.to_string_lossy().to_string();
            }
            String::new()
        });

    if llama_build.is_empty() {
        println!("cargo:warning=llama.cpp not found. Build: cd leafcutter/llama.cpp && mkdir -p build && cd build && cmake .. -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=ON -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=OFF -DLLAMA_CURL=OFF && make -j$(nproc)");
        return;
    }

    // Try static libs first (preferred for self-contained binary)
    let static_llama = Path::new(&llama_build).join("src/libllama.a");
    let static_ggml = Path::new(&llama_build).join("ggml/src/libggml.a");

    if static_llama.exists() && static_ggml.exists() {
        // Static linking — add both directories
        let llama_src = Path::new(&llama_build).join("src");
        let ggml_src = Path::new(&llama_build).join("ggml/src");
        println!("cargo:rustc-link-search=native={}", llama_src.display());
        println!("cargo:rustc-link-search=native={}", ggml_src.display());

        // Link order: static libs first (dependencies after dependents)
        println!("cargo:rustc-link-lib=static=llama");
        println!("cargo:rustc-link-lib=static=ggml");
        println!("cargo:rustc-link-lib=static=ggml-cpu");
        println!("cargo:rustc-link-lib=static=ggml-base");

        // System dependencies required by llama.cpp static builds
        println!("cargo:rustc-link-lib=dylib=gomp");
        println!("cargo:rustc-link-lib=dylib=stdc++");
        println!("cargo:rustc-link-lib=dylib=m");
        println!("cargo:rustc-link-lib=dylib=pthread");
        println!("cargo:rustc-link-lib=dylib=dl");
        println!("cargo:rustc-link-lib=dylib=z");

        println!("cargo:warning=llama.cpp statically linked from {}", llama_build);
        return;
    }

    // Fallback: try shared libs in bin/ (our build layout) or flat (Ollama layout)
    let so_bin = Path::new(&llama_build).join("bin/libllama.so");
    let so_flat = Path::new(&llama_build).join("libllama.so");

    let effective_lib_dir = if so_bin.exists() {
        format!("{}/bin", llama_build)
    } else if so_flat.exists() {
        llama_build.clone()
    } else {
        println!("cargo:warning=libllama.so not found in {}", llama_build);
        return;
    };

    println!("cargo:rustc-link-search=native={}", effective_lib_dir);
    println!("cargo:rustc-link-lib=dylib=llama");
    println!("cargo:rustc-link-lib=dylib=ggml");
    if Path::new(&format!("{}/libggml-base.so", effective_lib_dir)).exists() {
        println!("cargo:rustc-link-lib=dylib=ggml-base");
    }
    if Path::new(&format!("{}/libggml-cpu.so", effective_lib_dir)).exists() {
        println!("cargo:rustc-link-lib=dylib=ggml-cpu");
    }
    println!("cargo:rustc-link-arg=-Wl,-rpath,{}", effective_lib_dir);
    println!("cargo:warning=llama.cpp dynamically linked from {}", effective_lib_dir);
}
