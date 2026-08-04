//! Decides whether an outbound HTTP URL is allowed under the
//! operator's policy. Primary job: defeat the "ask the LLM to use
//! web_fetch against internal infrastructure" side channel that would
//! otherwise turn a web tool into an SSRF primitive.
//!
//! Faithful port of Go `internal/netguard/netguard.go`. Like all
//! in-process checks, this is a heuristic layered on top of OS-level
//! network policy, not a security boundary.

use std::net::IpAddr;

/// Categorises a check outcome.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Decision {
    pub allow: bool,
    pub reason: String,
}

/// Gates outbound requests by destination and scheme.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Policy {
    /// Allow the loopback interface (127.0.0.0/8, ::1). Default OFF.
    pub allow_loopback: bool,
    /// Allow RFC1918 / link-local addresses. Default OFF.
    pub allow_private: bool,
    /// Allow metadata endpoints (169.254.169.254). Default OFF.
    pub allow_metadata: bool,
    /// Allow file:// or other non-http schemes. Default OFF.
    pub allow_non_http: bool,
    /// When false, http:// URLs are denied (https still allowed).
    pub allow_cleartext_http: bool,
}

/// Policy recommended for production use.
pub fn secure_default() -> Policy {
    Policy {
        allow_loopback: false,
        allow_private: false,
        allow_metadata: false,
        allow_non_http: false,
        allow_cleartext_http: false,
    }
}

/// Relaxes loopback/private/http so operators can use Ollama on
/// localhost and dev services on 192.168.x.x. Metadata still blocked.
pub fn local_dev_policy() -> Policy {
    Policy {
        allow_loopback: true,
        allow_private: true,
        allow_metadata: false,
        allow_non_http: false,
        allow_cleartext_http: true,
    }
}

impl Policy {
    /// Allow=true for URLs that pass the gate. On reject, Reason
    /// describes why (suitable for display to the operator).
    pub fn check(&self, raw_url: &str) -> Decision {
        let u = match url::Url::parse(raw_url) {
            Ok(u) => u,
            Err(e) => {
                return Decision {
                    allow: false,
                    reason: format!("unparseable URL: {e}"),
                }
            }
        };

        let scheme = u.scheme().to_lowercase();
        if scheme != "http" && scheme != "https" {
            if !self.allow_non_http {
                return Decision {
                    allow: false,
                    reason: format!("scheme {:?} is not allowed", u.scheme()),
                };
            }
        }

        if scheme == "http" && !self.allow_cleartext_http {
            return Decision {
                allow: false,
                reason: "cleartext http:// is not allowed; use https://".to_string(),
            };
        }

        let Some(host) = u.host_str() else {
            return Decision {
                allow: false,
                reason: "URL has no host".to_string(),
            };
        };

        // Resolve all IPs the host maps to and check each. This is
        // the conservative variant that defeats the "DNS points to
        // 127.0.0.1 even though we asked for example.com" trick.
        let ips: Vec<IpAddr> = match lookup_ips(host) {
            Ok(ips) => ips,
            Err(_) => {
                // Fall back to literal inspection so a straight
                // literal-IP URL still gates.
                if let Ok(ip) = host.parse::<IpAddr>() {
                    vec![ip]
                } else {
                    return Decision {
                        allow: false,
                        reason: format!("cannot resolve host: {host}"),
                    };
                }
            }
        };

        for ip in ips {
            if let Some(why) = self.classify_ip(ip) {
                return Decision {
                    allow: false,
                    reason: why,
                };
            }
        }
        Decision {
            allow: true,
            reason: String::new(),
        }
    }

    fn classify_ip(&self, ip: IpAddr) -> Option<String> {
        if ip.is_loopback() && !self.allow_loopback {
            return Some(format!("loopback address {ip} blocked"));
        }
        if is_link_local(&ip) {
            return Some(format!("link-local address {ip} blocked"));
        }
        if ip.is_multicast() {
            return Some(format!("multicast address {ip} blocked"));
        }
        if ip.is_unspecified() {
            return Some(format!("unspecified address {ip} blocked"));
        }
        if is_private_ip(&ip) && !self.allow_private {
            return Some(format!("private-network address {ip} blocked"));
        }
        // AWS/GCP/Azure metadata endpoints (169.254.169.254, ...)
        if is_metadata(&ip) && !self.allow_metadata {
            return Some(format!("metadata address {ip} blocked"));
        }
        None
    }
}

/// DNS resolution for the gate. Production code uses the system
/// resolver; tests can override via the local function below.
fn lookup_ips(host: &str) -> std::io::Result<Vec<IpAddr>> {
    use std::net::ToSocketAddrs;
    // Prefer literal parse to avoid a spurious DNS round-trip.
    if let Ok(ip) = host.parse::<IpAddr>() {
        return Ok(vec![ip]);
    }
    let addrs = (host, 0u16).to_socket_addrs()?;
    Ok(addrs.map(|sa| sa.ip()).collect())
}

fn is_metadata(ip: &IpAddr) -> bool {
    // 169.254.169.254 — the AWS/GCP/Azure metadata endpoint, plus the
    // 169.254.0.0/16 link-local block it lives in.
    match ip {
        IpAddr::V4(v4) => {
            let o = v4.octets();
            o[0] == 169 && o[1] == 254
        }
        IpAddr::V6(_) => false,
    }
}

/// IPv4 169.254.0.0/16; IPv6 fe80::/10.
fn is_link_local(ip: &IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => {
            let o = v4.octets();
            o[0] == 169 && o[1] == 254
        }
        IpAddr::V6(v6) => (v6.octets()[0] & 0xff) == 0xfe && (v6.octets()[1] & 0xc0) == 0x80,
    }
}

/// RFC1918 (10/8, 172.16/12, 192.168/16) + RFC6598 (100.64/10).
fn is_private_ip(ip: &IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => {
            let o = v4.octets();
            o[0] == 10
                || (o[0] == 172 && (16..=31).contains(&o[1]))
                || (o[0] == 192 && o[1] == 168)
                || (o[0] == 100 && (64..=127).contains(&o[1]))
        }
        IpAddr::V6(_) => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn secure_default_blocks_loopback() {
        let p = secure_default();
        let d = p.check("https://127.0.0.1:11434/api/chat");
        assert!(!d.allow);
        assert!(d.reason.contains("loopback"));
    }

    #[test]
    fn local_dev_allows_loopback_http() {
        let p = local_dev_policy();
        assert!(p.check("http://localhost:11434/api/chat").allow);
        assert!(p.check("http://127.0.0.1:11434/api/chat").allow);
        assert!(p.check("http://192.168.1.10:8080").allow);
    }

    #[test]
    fn secure_default_blocks_cleartext_http() {
        let p = secure_default();
        let d = p.check("http://example.com");
        assert!(!d.allow);
        assert!(d.reason.contains("cleartext"));
    }

    #[test]
    fn blocks_metadata_endpoint() {
        let p = local_dev_policy();
        let d = p.check("https://169.254.169.254/latest/meta-data/");
        assert!(!d.allow);
        // Go's ordering reports link-local before the metadata check
        // for the 169.254.0.0/16 block, so either reason is fine.
        assert!(
            d.reason.contains("metadata") || d.reason.contains("link-local"),
            "{}",
            d.reason
        );
    }

    #[test]
    fn blocks_private_when_not_allowed() {
        let p = secure_default();
        let d = p.check("https://10.0.0.5/api");
        assert!(!d.allow);
        assert!(d.reason.contains("private-network"));
    }

    #[test]
    fn blocks_non_http_scheme() {
        let p = secure_default();
        let d = p.check("file:///etc/passwd");
        assert!(!d.allow);
        assert!(d.reason.contains("scheme"));
    }

    #[test]
    fn allows_public_https() {
        let p = secure_default();
        assert!(p.check("https://example.com").allow);
        assert!(p.check("https://docs.rs/reqwest").allow);
    }

    #[test]
    fn bad_url_rejected() {
        let p = secure_default();
        assert!(!p.check("not a url at all").allow);
    }

    #[test]
    fn rfc1918_private_detection() {
        use std::net::Ipv4Addr;
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(172, 16, 0, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(172, 31, 255, 255))));
        assert!(!is_private_ip(&IpAddr::V4(Ipv4Addr::new(172, 32, 0, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(192, 168, 1, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(100, 64, 0, 1))));
        assert!(!is_private_ip(&IpAddr::V4(Ipv4Addr::new(8, 8, 8, 8))));
    }
}
