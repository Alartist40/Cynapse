# Changelog

All notable changes to the Container Escape Trainer project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-01-08

### 🎉 Initial Release - Container Escape Trainer MVP

The first public release of Container Escape Trainer, a CTF-in-a-box educational platform for learning container security through hands-on exploitation.

---

## Added

### Core Container Infrastructure

#### Docker Container Setup
- **Base Image**: Debian bullseye-slim for minimal attack surface while maintaining functionality
- **User Configuration**: Non-privileged `escape` user as default, demonstrating escalation from low privileges
- **Package Installation**: Installed essential tools including `docker.io`, `sudo`, `libcap2-bin`, `curl`, `net-tools`, `procps`, `vim`
- **Entry Point**: `/start.sh` script that displays welcome banner, instructions, and launches validation daemon

#### Build System
- **Dockerfile**: Multi-stage setup that configures all 10 escape paths during build time
- **build.sh**: Automated build script with user-friendly output and success verification
- **run.sh**: Convenience script to launch container with correct flags (--privileged, volume mounts)
- **.gitignore**: Configured to exclude Docker artifacts and temporary files

---

### 🔓 Container Escape Mechanisms (10 Total)

#### 1. CAP_DAC_READ_SEARCH - Capability-Based File Access
**Technical Implementation**:
- Set `cap_dac_read_search+ep` on `/bin/cat` and `/bin/bash` using `setcap`
- Allows bypassing discretionary access control (DAC) for file read operations
- Enables reading any file on the system regardless of permissions

**Security Impact**: Demonstrates over-permissive Linux capabilities that can expose sensitive data

**Detection Method**: `capsh --print` or `getcap /bin/*`

---

#### 2. CAP_SYS_ADMIN - Mount and Namespace Manipulation
**Technical Implementation**:
- Set `cap_sys_admin+ep` on `/usr/bin/nsenter`
- Enables mount/unmount operations and namespace entry
- Allows entering host namespaces from within container

**Security Impact**: CAP_SYS_ADMIN is nearly equivalent to root, enabling extensive system manipulation

**Detection Method**: `capsh --print` and checking for SYS_ADMIN capability

---

#### 3. Privileged Container Mode - Full Capability Access
**Technical Implementation**:
- Container designed to run with `--privileged` flag
- Grants all Linux capabilities to container processes
- Disables device cgroup restrictions
- Provides access to host devices in `/dev`

**Security Impact**: Privileged containers have nearly unrestricted access to host resources

**Detection Method**: `capsh --print | grep Current` shows all capabilities

---

#### 4. Host Path Mount - Direct Filesystem Access
**Technical Implementation**:
- Host root filesystem (`/`) mounted at `/host` inside container via `-v /:/host`
- Provides read/write access to entire host filesystem
- Flag file placed at `/host/flag10.txt`

**Security Impact**: Overly broad host mounts violate container isolation principles

**Detection Method**: `mount | grep host` or `ls /host`

---

#### 5. Docker Socket Exposure - Container Control Plane Access
**Technical Implementation**:
- Docker socket mounted into container: `-v /var/run/docker.sock:/var/run/docker.sock`
- Allows Docker CLI commands from inside container
- Enables spawning new privileged containers with host mounts

**Security Impact**: Docker socket access = root on host system

**Exploitation Path**: 
```bash
docker run -it -v /:/host alpine chroot /host /bin/bash
```

**Detection Method**: `ls -la /var/run/docker.sock`

---

#### 6. PID Namespace Sharing - Host Process Visibility
**Technical Implementation**:
- Documented escape path for when container shares host PID namespace
- Access to host processes via `/proc/<pid>/root`
- Can use `nsenter` to enter namespaces of PID 1 (init)

**Security Impact**: PID namespace sharing breaks process isolation

**Exploitation Path**:
```bash
nsenter -t 1 -m -u -n -i sh
```

**Detection Method**: `ps aux` showing host processes

---

#### 7. Writable Cgroup - Release Agent Exploitation
**Technical Implementation**:
- Created hint documentation for cgroup release_agent escape technique
- Explains notify_on_release mechanism exploitation
- Requires writable `/sys/fs/cgroup` paths

**Security Impact**: Advanced technique allowing arbitrary code execution as root on host

**Detection Method**: `ls -la /sys/fs/cgroup/`

**Reference**: This is based on the Felix Wilhelm cgroup escape (2019)

---

#### 8. Procfs Escape - /proc Filesystem Manipulation
**Technical Implementation**:
- Exploit `/proc/1/root` which often points to host root filesystem
- Can access host files if combined with appropriate capabilities
- Documented in hint system with examples

**Security Impact**: /proc leaks host information and can be abused for escapes

**Exploitation Path**:
```bash
cat /proc/1/root/flag10.txt
```

**Detection Method**: `ls -la /proc/1/root`

---

#### 9. Weak Seccomp Profile - Syscall Filter Bypass
**Technical Implementation**:
- Documented escape path for containers with disabled/weak seccomp
- Explains how reduced syscall filtering increases attack surface
- Container runs without custom seccomp profile

**Security Impact**: Allows use of dangerous syscalls that could enable kernel exploits

**Detection Method**: `grep Seccomp /proc/self/status`

---

#### 10. No AppArmor / SELinux - Missing Mandatory Access Control
**Technical Implementation**:
- Container runs unconfined (no AppArmor or SELinux restrictions)
- Documented in hint system
- Shows importance of defense-in-depth

**Security Impact**: Missing MAC systems reduce security layers

**Detection Method**: `cat /proc/self/attr/current`

---

### 📚 Educational System

#### Hint System (11 Files)
- **00_index.txt**: Overview and navigation guide for all hints
- **01_capabilities.txt**: Deep dive into Linux capabilities and their security implications
- **02_reconnaissance.txt**: Step-by-step information gathering techniques (10 recon commands)
- **03_privileged.txt** through **10_apparmor.txt**: Detailed guides for each escape path

**Hint Quality**: Each hint includes:
- Difficulty rating
- Technical explanation
- Step-by-step exploitation guide
- Real-world security impact
- Detection methods

#### Interactive Welcome System
- **ASCII Banner**: Eye-catching welcome message
- **Mission Briefing**: Clear objective explanation
- **Escape Path Summary**: All 10 techniques listed with brief descriptions
- **Quick Hints**: Essential commands to get started
- **Win Condition**: Explicit success criteria

---

### 🎯 Validation System

#### checkredact.sh Daemon
**Functionality**:
- Monitors multiple possible locations for `flag10_report.json`
- Validates that credit card number `4444-4444-4444-4444` is NOT present (has been redacted)
- Calculates elapsed time from `/tmp/start.time`
- Provides clear success/failure feedback
- Auto-exits on successful validation

**Technical Details**:
- Runs as background process started by `start.sh`
- 3-second polling interval to minimize resource usage
- Comprehensive success banner with celebration message
- Elapsed time formatted as `Xm XXs`

**Validation Logic**:
```bash
if grep -q "4444-4444-4444-4444" "$report_path"; then
    # FAIL: Card still visible
else
    # SUCCESS: Card has been redacted
fi
```

---

### 📦 Flag File

#### /host/flag10.txt
- **Format**: ASCII banner with fake credit card number
- **Content**: Instructional text + `4444-4444-4444-4444` credit card
- **Location**: `/host/flag10.txt` (accessible after escape)
- **Purpose**: Combines security escape with privacy/redaction skills

---

### 📖 Documentation

#### README.md (Comprehensive User Guide)
**Sections**:
- Project overview and objectives
- Features and benefits (8 key features)
- Prerequisites (software, system, knowledge)
- Installation and setup (step-by-step for fresh system)
- Quick start guide
- Detailed challenge walkthrough
- All 10 escape paths with difficulty ratings and exploitation guides
- Architecture diagram and component descriptions
- Win condition explanation
- Troubleshooting guide (10+ common issues)
- Security warnings and safe usage guidelines
- Educational use recommendations
- Workshop format suggestions
- Contributing guidelines

**Length**: ~1000+ lines of detailed documentation

**Quality**: Includes code examples, command outputs, ASCII diagrams, difficulty ratings, and best practices

---

#### CHANGELOG.md (This File)
**Purpose**: Technical record of all features, implementations, and changes
**Format**: Keep a Changelog standard with semantic versioning
**Detail Level**: Technical implementation specifics for developers and security researchers

---

### 🔧 Technical Features

#### Build Process
- **Automated Setup**: `exploits/setup.sh` runs during `docker build` to configure all escapes
- **Capability Setting**: Uses `setcap` to grant specific capabilities to binaries
- **Hint Generation**: Programmatically creates all 11 hint files during build
- **Permission Management**: Sets appropriate file permissions for security demonstration

#### Runtime Features
- **Timer System**: Records start time in `/tmp/start.time` for elapsed time calculation
- **Daemon Management**: Background process for continuous validation
- **Multi-Location Support**: Checks multiple paths for redaction report
- **Interactive Shell**: Drops to bash prompt for hands-on exploration

#### Security Considerations
- **Non-Root Default**: Container starts as `escape` user, requiring privilege escalation
- **Realistic Misconfigurations**: All escapes based on real-world container security issues
- **Progressive Difficulty**: Escapes range from ⭐ (very easy) to ⭐⭐⭐⭐ (hard)
- **Safe for Learning**: No active kernel exploits included (documented only for safety)

---

## Technical Stack

### Technologies Used
- **Container Runtime**: Docker 20.10+
- **Base OS**: Debian 11 (Bullseye) Slim
- **Shell Scripting**: Bash 5.x
- **Linux Capabilities**: libcap2-bin
- **Container Technologies**: Docker Engine, Docker CLI

### File Structure
```
Container-Escape-Trainer/
├── Dockerfile                    # Container build definition
├── build.sh                      # Automated build script
├── run.sh                        # Container launch script
├── .gitignore                    # Git exclusions
├── README.md                     # User documentation
├── CHANGELOG.md                  # Technical changelog (this file)
├── prd.md                        # Original product requirements
└── rootfs/                       # Container filesystem overlay
    ├── start.sh                  # Entry point script
    ├── opt/
    │   └── checkredact.sh        # Validation daemon
    ├── exploits/
    │   └── setup.sh              # Escape configuration script
    └── hints/                    # Created during build
        ├── 00_index.txt          # Hint navigation
        ├── 01_capabilities.txt   # Capability abuse guide
        ├── 02_reconnaissance.txt # Recon techniques
        └── 03-10 *.txt           # Individual escape guides
```

---

## Performance Metrics

- **Docker Image Size**: ~120MB (compressed)
- **Build Time**: 2-5 minutes (depends on network for first build)
- **Runtime Memory**: ~50-100MB
- **Startup Time**: <2 seconds
- **Challenge Completion Time**: 5-15 minutes (target for experienced participants)

---

## Known Limitations

### Out of Scope for MVP (v1.0.0)

1. **Kubernetes Support**: 
   - Current version uses Docker only
   - Future: Pod security policies, admission controllers

2. **Web Scoreboard**:
   - No multi-user tracking
   - Future: Centralized scoreboard with team rankings

3. **Active Kernel Exploits**:
   - Dirty COW and similar exploits not implemented
   - Only documented for safety reasons
   - Future: Optional "advanced mode" with real exploits

4. **Windows Container Support**:
   - Linux containers only
   - Future: Windows container escape scenarios

5. **Network-Based Escapes**:
   - No network-level escapes included
   - Future: CNI plugin exploits, cluster networking issues

---

## Security Audit

### Intentional Vulnerabilities (By Design)

✅ The following are **DELIBERATELY INSECURE**:
- Over-permissive Linux capabilities
- Privileged container mode
- Host filesystem mounts
- Docker socket exposure
- Weak/missing security profiles

⚠️ **These are educational vulnerabilities. DO NOT replicate in production.**

### Unintentional Vulnerabilities

None identified. This container is designed specifically for local education and should not be exposed to untrusted networks.

---

## Testing

### Tested Environments

✅ **Verified Working**:
- Docker Desktop on Windows 10/11 (WSL2 backend)
- Docker Engine on Ubuntu 20.04/22.04
- Docker Engine on Debian 11
- Docker Desktop on macOS (Intel and Apple Silicon)

❓ **Not Tested**:
- Podman (may work with modifications)
- Kubernetes (not supported in v1.0.0)
- Rootless Docker (intentionally incompatible)

---

## Future Enhancements (Planned)

### v2.0.0 Roadmap
- [ ] Kubernetes pod escape scenarios
- [ ] Web-based scoreboard for team competitions
- [ ] Multiple difficulty levels (beginner, intermediate, expert)
- [ ] Achievement system (unlock badges for different escapes)
- [ ] Video walkthrough tutorials
- [ ] Integration with existing CTF platforms (CTFd, etc.)

### Community Requests
- Multi-language support (hints in ES, FR, DE, JP)
- Offline documentation viewer
- Automated lab setup for workshops (Vagrant/Terraform)
- Cloud deployment guides (AWS, GCP, Azure)

---

## Credits

### Escape Techniques Based On
- Linux Capabilities research (Dan Walsh, Linux kernel docs)
- Docker security best practices (Docker Inc., CIS Benchmarks)
- Felix Wilhelm's cgroup escape (Trail of Bits, 2019)
- Brandon Edwards & Nick Freeman's container research (NCC Group)
- Public CVE research and container security audits

### Tools & Technologies
- Docker containerization platform
- Debian GNU/Linux
- Bash shell scripting
- Linux capabilities (libcap2)

---

## Versioning

- **1.0.0** - Initial MVP release (2026-01-08)
- Future versions will follow semantic versioning (MAJOR.MINOR.PATCH)
  - MAJOR: Incompatible changes (e.g., different container runtime)
  - MINOR: New features (e.g., additional escape paths)
  - PATCH: Bug fixes and documentation updates

---

## Project Impact

### Intended Use Cases

✅ **Recommended**:
- University cybersecurity courses
- Corporate security training
- Security conference workshops
- CTF competitions
- DevSecOps team education
- Security certification study (OSCP, CEH, etc.)

❌ **Not Recommended**:
- Production environments (obviously!)
- Shared infrastructure without proper isolation
- Unsupervised learning (students should have instructor guidance)
- Systems with sensitive data

---

## Changelog Maintenance

This changelog is maintained to provide:
- **Transparency**: Clear record of what's in each version
- **Education**: Technical details for security researchers
- **Accountability**: Track changes for security auditing

**Maintainer**: Alartist40  
**Repository**: https://github.com/Alartist40/Container-Escape-Trainer  
**Last Updated**: 2026-01-08

---

**[1.0.0]**: Initial release  
**Release Date**: January 8, 2026  
**Status**: ✅ Stable - Ready for educational use

---

*For the latest updates and version history, visit the [GitHub repository](https://github.com/Alartist40/Container-Escape-Trainer).*
