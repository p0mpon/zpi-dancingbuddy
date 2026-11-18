const THRESHOLDS = {
    TIMESTAMP_WINDOW_THRESHOLD: 0.2,
    TIMESTAMP_TOLERANCE_THRESHOLD: 0.07,

    HIP_HEIGHT_TOLERANCE_THRESHOLD: 0.15,
    HIP_HEIGHT_GRACE_THRESHOLD: 0.05,

    ANGLE_GRACE_THRESHOLD: 15.0,
    ANGLE_TOLERANCE_THRESHOLD: 45.0,

    VELOCITY_GRACE_THRESHOLD_PERCENT: 5.0,
    VELOCITY_TOLERANCE_THRESHOLD_PERCENT: 20.0,

    ACCELERATION_GRACE_THRESHOLD_PERCENT: 10.0,
    ACCELERATION_TOLERANCE_THRESHOLD_PERCENT: 30.0,

    JOINTS_SCORE_WEIGHT: 0.85,
    GLOBAL_POSITION_SCORE_WEIGHT: 0.15,
};

function getFixedSimilarity(diff, grace, tolerance) {
    const difference = Math.abs(diff);
    if (difference <= grace) return 1.0;
    if (difference >= tolerance) return 0.0;
    return (tolerance - difference) / (tolerance - grace);
}

function getRelativeSimilarity(diff, baseValue, gracePercent, tolerancePercent) {
    const baseAbs = Math.abs(baseValue);
    const grace = baseAbs * (gracePercent / 100.0);
    const tolerance = baseAbs * (tolerancePercent / 100.0);
    return getFixedSimilarity(diff, grace, tolerance);
}

export function compareLiveFrames(baseFrame, liveFrame) {
    let globalScore = 0.0;
    // NEW: Tracker for lost points
    let losses = { angle: 0, velocity: 0, acceleration: 0, hipHeight: 0, hipRotation: 0 };

    const hasGlobal = baseFrame.global_position &&
        (baseFrame.global_position.hip_y !== null || baseFrame.global_position.body_rotation_deg !== null);

    if (hasGlobal) {
        const globalScores = [];
        if (baseFrame.global_position.hip_y !== null && liveFrame.hip_height != null) {
            const sim = getFixedSimilarity(
                baseFrame.global_position.hip_y - liveFrame.hip_height,
                THRESHOLDS.HIP_HEIGHT_GRACE_THRESHOLD,
                THRESHOLDS.HIP_HEIGHT_TOLERANCE_THRESHOLD
            );
            globalScores.push(sim);
            losses.hipHeight += (1.0 - sim); // Track penalty
        }
        if (baseFrame.global_position.body_rotation_deg !== null && liveFrame.hip_rotation != null) {
            const sim = getFixedSimilarity(
                baseFrame.global_position.body_rotation_deg - liveFrame.hip_rotation,
                THRESHOLDS.ANGLE_GRACE_THRESHOLD,
                THRESHOLDS.ANGLE_TOLERANCE_THRESHOLD
            );
            globalScores.push(sim);
            losses.hipRotation += (1.0 - sim); // Track penalty
        }
        globalScore = globalScores.length > 0 ? globalScores.reduce((a, b) => a + b, 0) / globalScores.length : 0.0;
    }

    let weightedJointsScore = 0.0;
    let jointsVisibilityWeight = 0.0;

    for (const [name, baseJoint] of Object.entries(baseFrame.joints)) {
        const compareJoint = liveFrame.joints[name];
        if (!compareJoint || baseJoint.visibility === 0 || compareJoint.visibility === 0) continue;

        let score = 0.0;
        if (compareJoint.angle != null) {
            const sim = getFixedSimilarity(
                baseJoint.angle - compareJoint.angle,
                THRESHOLDS.ANGLE_GRACE_THRESHOLD,
                THRESHOLDS.ANGLE_TOLERANCE_THRESHOLD
            );
            const weight = baseJoint.dynamic_weights.angle_weight;
            score += sim * weight;
            losses.angle += (1.0 - sim) * weight * baseJoint.visibility;
        }
        if (compareJoint.angular_velocity != null) {
            const sim = getRelativeSimilarity(
                baseJoint.velocity_deg_per_sec - compareJoint.angular_velocity,
                baseJoint.velocity_deg_per_sec,
                THRESHOLDS.VELOCITY_GRACE_THRESHOLD_PERCENT,
                THRESHOLDS.VELOCITY_TOLERANCE_THRESHOLD_PERCENT
            );
            const weight = baseJoint.dynamic_weights.kinematic_weight * 0.5;
            score += sim * weight;
            losses.velocity += (1.0 - sim) * weight * baseJoint.visibility;
        }
        if (compareJoint.angular_acceleration != null) {
            const sim = getRelativeSimilarity(
                baseJoint.acceleration_deg_per_sec2 - compareJoint.angular_acceleration,
                baseJoint.acceleration_deg_per_sec2,
                THRESHOLDS.ACCELERATION_GRACE_THRESHOLD_PERCENT,
                THRESHOLDS.ACCELERATION_TOLERANCE_THRESHOLD_PERCENT
            );
            const weight = baseJoint.dynamic_weights.kinematic_weight * 0.5;
            score += sim * weight;
            losses.acceleration += (1.0 - sim) * weight * baseJoint.visibility;
        }

        weightedJointsScore += score * baseJoint.visibility;
        jointsVisibilityWeight += baseJoint.visibility;
    }

    let jointsScore = jointsVisibilityWeight > 0 ? (weightedJointsScore / jointsVisibilityWeight) : 0.0;

    if (hasGlobal) {
        globalScore *= THRESHOLDS.GLOBAL_POSITION_SCORE_WEIGHT;
        jointsScore *= THRESHOLDS.JOINTS_SCORE_WEIGHT;

        // Scale global losses by their ultimate weight
        losses.hipHeight *= THRESHOLDS.GLOBAL_POSITION_SCORE_WEIGHT;
        losses.hipRotation *= THRESHOLDS.GLOBAL_POSITION_SCORE_WEIGHT;
    }

    // MODIFIED RETURN: Now returning an object with the breakdown
    return {
        score: globalScore + jointsScore,
        breakdown: losses
    };
}