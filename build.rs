fn main() {
    let ollama_lib = "/usr/local/lib/ollama";
    if std::path::Path::new(ollama_lib).exists() {
        println!("cargo:rustc-link-search=native={}", ollama_lib);
        println!("cargo:rustc-link-arg=-Wl,-rpath,{}", ollama_lib);
    }
}
