import { authApi, defaultApi } from "./axios_instances";

export const API_ENDPOINTS = {
    "register": "register/",
    "login": "login/",
    "logout": "logout/",
    "user": "user/",
    "videos": "videos/",
    "video_details": (id) => `videos/${id}/`,
    "video_analysis": (id) => `videos/${id}/analysis/`,
    "video_stream": (id) => `videos/${id}/stream/`,
    "video_thumbnail": (id) => `videos/${id}/thumbnail/`,
    "dance_attempts": "dance-attempts/",
};

export async function getAllVideos() {
    try {
        const response = await defaultApi.get(API_ENDPOINTS.videos);
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function postVideo(video) {
    try {
        const response = await defaultApi.post(API_ENDPOINTS.videos, video);
        return response.data;
    } catch (e) {
        console.error("error details:", e.response?.data);
        throw e;
    }
}

export async function getVideoAnalysis(id) {
    try {
        const response = await defaultApi.get(API_ENDPOINTS.video_analysis(id));
        return response.data;
    } catch (e) {
        console.error("Failed to fetch reference analysis:", e);
        throw e;
    }
}

export async function postDanceAttempt(referenceVideoId, frames, videoBlob) {
    try {
        const formData = new FormData();
        formData.append('reference_video_id', referenceVideoId);
        formData.append('json_analysis', JSON.stringify(frames));
        formData.append('video_file', videoBlob, 'practice_attempt.webm');

        const response = await defaultApi.post(API_ENDPOINTS.dance_attempts, formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        return response.data;
    } catch (e) {
        console.error("error details:", e.response?.data);
        throw e;
    }
}

export async function getDanceAttemptStatus(taskId) {
    try {
        const response = await defaultApi.get(API_ENDPOINTS.dance_attempt_status(taskId));
        return response.data;
    } catch (e) {
        console.error("Failed to fetch score status:", e);
        throw e;
    }
}

export async function getVideo(id) {
    try {
        const response = await defaultApi.get(API_ENDPOINTS.video_details(id));
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function getFullVideo(id) {
    try {
        const response = await defaultApi.get(API_ENDPOINTS.video_details(id));
        const stream_response = await defaultApi.get(API_ENDPOINTS.video_stream(id), {
            responseType: 'blob'
        });

        const blob = URL.createObjectURL(stream_response.data);

        return {
            ...response.data,
            file: blob
        };
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function editVideo(id, videoData) {
    try {
        const response = await defaultApi.put(API_ENDPOINTS.video_details(id, videoData));
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function deleteVideo(id) {
    try {
        const response = await defaultApi.delete(API_ENDPOINTS.video_details(id));
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function loginUser(username, password) {
    try {
        const response = await authApi.post('login/', {
            username: username,
            password: password
        });
        return response.data;
    } catch (error) {
        return false;
    }
}

export async function getUser(id) {
    try {
        const response = await authApi.get(API_ENDPOINTS.user);
        return response.data;
    } catch (error) {
        return false;
    }
}