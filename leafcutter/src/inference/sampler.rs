use rand::Rng;

pub fn sample_top_p(logits: &[f32], temperature: f32, top_p: f32) -> usize {
    let top_k: usize = std::env::var("LEAFCUTTER_TOP_K")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(20);
    sample_top_p_top_k(logits, temperature, top_p, top_k)
}

pub fn apply_repeat_penalty(logits: &mut [f32], recent_tokens: &[usize], penalty: f32) {
    if (penalty - 1.0).abs() < 1e-4 || penalty <= 0.0 || recent_tokens.is_empty() {
        return;
    }
    for &t in recent_tokens {
        if t < logits.len() {
            if logits[t] <= 0.0 {
                logits[t] *= penalty;
            } else {
                logits[t] /= penalty;
            }
        }
    }
}

pub fn sample_top_p_top_k(logits: &[f32], temperature: f32, top_p: f32, top_k: usize) -> usize {
    if temperature <= 0.0 {
        return logits.iter().enumerate().max_by(|(_, a), (_, b)| a.total_cmp(b)).map(|(i, _)| i).unwrap_or(0);
    }

    let len = logits.len();
    let mut max_logit = f32::NEG_INFINITY;
    for &v in logits.iter() {
        if v > max_logit { max_logit = v; }
    }

    let mut indices: Vec<usize> = (0..len).collect();
    let k = if top_k > 0 && top_k < len { top_k } else { len };
    indices.select_nth_unstable_by(k, |&a, &b| {
        let pa = (logits[a] - max_logit).exp();
        let pb = (logits[b] - max_logit).exp();
        pb.partial_cmp(&pa).unwrap_or(std::cmp::Ordering::Equal)
    });
    indices.truncate(k);

    let mut cumsum = 0.0f32;
    let exp_sum: f32 = indices.iter().map(|&i| (logits[i] - max_logit).exp()).sum();

    let mut rng = rand::thread_rng();
    let rand_val: f32 = rng.gen::<f32>();
    let mut cum = 0.0f32;
    for &i in &indices {
        cum += (logits[i] - max_logit).exp() / exp_sum;
        if cum >= rand_val {
            return i;
        }
    }
    indices[indices.len() - 1]
}
