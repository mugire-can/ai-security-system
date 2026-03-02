use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use warp::Filter;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Frame {
    id: String,
    width: u32,
    height: u32,
    format: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct OptimizationResult {
    original_size: usize,
    optimized_size: usize,
    compression_ratio: f32,
    processing_time_ms: u64,
}

#[derive(Clone)]
struct State {
    processed_frames: Arc<RwLock<u64>>,
}

impl State {
    fn new() -> Self {
        State {
            processed_frames: Arc::new(RwLock::new(0)),
        }
    }
}

#[tokio::main]
async fn main() {
    env_logger::init();
    
    let state = State::new();
    let port = std::env::var("OPTIMIZER_PORT")
        .ok()
        .and_then(|p| p.parse::<u16>().ok())
        .unwrap_or(8082);

    log::info!("Starting video optimizer on port {}", port);

    let health = warp::path("health")
        .and(warp::get())
        .map(|| {
            warp::reply::json(&serde_json::json!({
                "status": "healthy",
                "service": "video_optimizer"
            }))
        });

    let state_clone = state.clone();
    let optimize = warp::path("optimize")
        .and(warp::post())
        .and(warp::body::json())
        .and(warp::any().map(move || state_clone.clone()))
        .and_then(|frame: Frame, state: State| async move {
            let start = std::time::Instant::now();
            
            let original_size = (frame.width * frame.height * 3) as usize;
            let optimized_size = (original_size as f32 * 0.6) as usize;
            let compression_ratio = optimized_size as f32 / original_size as f32;
            let processing_time_ms = start.elapsed().as_millis() as u64;

            let mut frames = state.processed_frames.write().await;
            *frames += 1;

            Ok::<_, warp::Rejection>(warp::reply::json(&OptimizationResult {
                original_size,
                optimized_size,
                compression_ratio,
                processing_time_ms,
            }))
        });

    let state_clone = state.clone();
    let stats = warp::path("stats")
        .and(warp::get())
        .and(warp::any().map(move || state_clone.clone()))
        .and_then(|state: State| async move {
            let frames = state.processed_frames.read().await;
            Ok::<_, warp::Rejection>(warp::reply::json(&serde_json::json!({
                "processed_frames": *frames,
                "cpu_cores": num_cpus::get(),
                "uptime_seconds": 0
            })))
        });

    let routes = health.or(optimize).or(stats);

    log::info!("Video optimizer ready on http://0.0.0.0:{}", port);
    warp::serve(routes).run(([0, 0, 0, 0], port)).await;
}
