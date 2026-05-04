# 📥 File Installation Guide

## Files You Downloaded

1. **install.sh** - One-command installer script
2. **main.go** - New CLI entry point with commands
3. **registry.go** - Synapse management system
4. **README.md** - Updated documentation

---

## 🗂️ Where To Place Each File

### 1. install.sh
**Location:** Root of your cynapse repository

```bash
cd ~/cynapse-final-fixed
# Or wherever your cynapse repo is

# Place file here
mv ~/Downloads/install.sh ./install.sh

# Make executable
chmod +x install.sh
```

---

### 2. main.go
**Location:** Replace existing `cmd/cynapse/main.go`

```bash
cd ~/cynapse-final-fixed

# Backup old main.go
cp cmd/cynapse/main.go cmd/cynapse/main.go.backup

# Replace with new one
mv ~/Downloads/main.go cmd/cynapse/main.go
```

---

### 3. registry.go
**Location:** Create new directory `internal/synapse/`

```bash
cd ~/cynapse-final-fixed

# Create synapse directory
mkdir -p internal/synapse

# Place file
mv ~/Downloads/registry.go internal/synapse/registry.go
```

---

### 4. README.md
**Location:** Root of repository (replace existing)

```bash
cd ~/cynapse-final-fixed

# Backup old README
cp README.md README.md.backup

# Replace
mv ~/Downloads/README.md ./README.md
```

---

## 🔧 Additional Changes Needed

### Update imports in main.go

The new `main.go` imports the synapse package. You need to make sure the import path matches your go.mod.

**In `main.go`, find this line:**
```go
"github.com/yourusername/cynapse/internal/synapse"
```

**Change it to match your actual module name from go.mod:**
```go
"github.com/Alartist40/cynapse/internal/synapse"
```

Or whatever your go.mod says.

---

### Update config package (if needed)

If your `internal/config/config.go` doesn't have `MCPServer` type, add this:

```go
// In internal/config/config.go

type MCPServer struct {
    Name    string            `yaml:"name"`
    Command string            `yaml:"command"`
    Args    []string          `yaml:"args"`
    Env     map[string]string `yaml:"env"`
}
```

---

## 🏗️ Final Directory Structure

After placing all files, your structure should look like:

```
cynapse/
├── install.sh                    # NEW - Installer script
├── README.md                     # UPDATED
├── cmd/
│   └── cynapse/
│       └── main.go              # UPDATED - CLI entry point
├── internal/
│   ├── synapse/                 # NEW DIRECTORY
│   │   └── registry.go          # NEW - Synapse system
│   ├── tui/
│   ├── agent/
│   ├── llm/
│   └── ...
├── config.yaml
└── go.mod
```

---

## 🧪 Test Installation

### 1. Test local build

```bash
cd ~/cynapse-final-fixed

# Build
go build -o cynapse ./cmd/cynapse

# Test help
./cynapse help

# Expected output:
# 🧠 CYNAPSE - Modular AI Agent
# USAGE:
#   cynapse                 Start interactive chat
#   ...
```

### 2. Test synapse commands

```bash
# List synapses (should be empty initially)
./cynapse synapse list

# Search available synapses
./cynapse synapse search
```

### 3. Test regular chat

```bash
# Run TUI
./cynapse

# Should start normally with your existing code
```

---

## 🚀 Push To GitHub

Once everything works locally:

```bash
cd ~/cynapse-final-fixed

git add .
git commit -m "Add one-command install and synapse system"
git push origin main
```

---

## 🎯 Test The Installer

After pushing to GitHub, test the installer:

```bash
# On a fresh machine or another directory
curl -fsSL https://raw.githubusercontent.com/Alartist40/cynapse/main/install.sh | bash

# Should:
# - Detect OS
# - Install dependencies
# - Build CYNAPSE
# - Install to /usr/local/bin/cynapse
# - Create ~/.cynapse/

# Then test
cynapse
```

---

## 🐛 Troubleshooting

### Issue: "package synapse is not in GOROOT"

**Solution:** Run `go mod tidy` to update dependencies

```bash
cd ~/cynapse-final-fixed
go mod tidy
go build -o cynapse ./cmd/cynapse
```

### Issue: "cannot find package config"

**Solution:** Make sure config package has the MCPServer type (see "Update config package" above)

### Issue: Install script fails to download Go

**Solution:** Install Go manually first:
```bash
# Linux
wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
```

---

## ✅ Verification Checklist

- [ ] install.sh in root directory and executable
- [ ] main.go replaced in cmd/cynapse/
- [ ] registry.go created in internal/synapse/
- [ ] README.md replaced
- [ ] Import paths updated to match go.mod
- [ ] `go mod tidy` ran successfully
- [ ] Local build works: `go build -o cynapse ./cmd/cynapse`
- [ ] Help works: `./cynapse help`
- [ ] Synapse commands work: `./cynapse synapse list`
- [ ] TUI works: `./cynapse`
- [ ] Pushed to GitHub
- [ ] Installer works from GitHub

---

## 🎉 You're Done!

Your CYNAPSE now has:
- ✅ One-command installation
- ✅ Modular synapse system
- ✅ Professional CLI commands
- ✅ Auto-detected OS setup

Users can now install with:
```bash
curl -fsSL https://raw.githubusercontent.com/Alartist40/cynapse/main/install.sh | bash
```

And extend with synapses:
```bash
cynapse synapse add leafcutter
```

Next: Convert LeafcutterLLM into a synapse! 🚀
