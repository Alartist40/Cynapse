//! Local web gateway — lets you log in from a browser, see the robot's camera,
//! and chat with the brain from inside the local network (or directly on the
//! robot). All traffic is served by the `cynapse` binary itself; nothing
//! leaves the machine.
//!
//! Endpoints:
//!   GET  /                  -> chat UI (HTML)
//!   GET  /stream            -> MJPEG camera stream (multipart/x-mixed-replace)
//!   GET  /camera.jpg        -> single JPEG frame (the latest from the feed)
//!   POST /api/chat          -> { message } -> { reply, route }   agent run
//!   POST /api/command       -> { name, args } -> raw tool call
//!   GET  /health            -> { status, version }
//!
//! Auth: when `gateway.auth_token` is set, the value must be supplied either
//! in the `X-Auth-Token` header or `?token=` query. When empty the gateway
//! is open (localhost-only by default — bind 0.0.0.0 only if you want it on
//! the LAN).

pub mod http;
pub mod state;

pub use http::run_server;
pub use state::GatewayState;
