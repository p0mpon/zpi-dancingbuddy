import {api} from "./axios_instances";
import {API_ENDPOINTS} from "./endpoints";
import {DANCE_ATTEMPT_PAGE_LIMIT, MAIN_PAGE_LIMIT} from "../utils/pagination";

export async function getAllVideos(searchQuery, difficulty, nextUrl) {
    try {
        if (nextUrl) {
            const response = await api.get(nextUrl)
            return response.data;
        }
        const params = {};

        params.limit = MAIN_PAGE_LIMIT;
        if (searchQuery) params.search = searchQuery;
        if (difficulty) params.difficulty = difficulty;

        const response = await api.get(API_ENDPOINTS.videos, {params});
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function uploadNewVideo(video) {
    try {
        const response = await api.post(API_ENDPOINTS.my_videos, video)
        return response.data;
    } catch (e) {
        console.error("error details:", e.response?.data);
        throw e;
    }
}

export async function getVideoDetails(id) {
    try {
        const response = await api.get(API_ENDPOINTS.video_details(id))
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function getFullVideo(id) {
    try {
        const response = await api.get(API_ENDPOINTS.video_details(id))
        const stream_response = await api.get(API_ENDPOINTS.video_stream(id), {
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

export async function getVideoAnalysis(id) {
    try {
        const response = await api.get(API_ENDPOINTS.video_analysis(id));
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

        const response = await api.post(API_ENDPOINTS.dance_attempts, formData, {
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

export async function editVideo(id, videoData) {
    try {
        const response = await api.put(API_ENDPOINTS.video_details(id, videoData))
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function deleteVideo(id) {
    try {
        const response = await api.delete(API_ENDPOINTS.video_details(id))
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

//--- auth endpoints ---

export async function loginUser(username, password) {
    try {
        const response = await api.post(API_ENDPOINTS.login, {
            username: username,
            password: password
        });
        return response.data;
    } catch (error) {
        return false;
    }
}

export async function getUser(nickname) {
    try {
        const response = await api.get(API_ENDPOINTS.public_profile(nickname))
        return response.data;
    } catch (error) {
        return false;
    }
}

export async function getDanceAttemptsForVideo(video_id, nextUrl) {
    try {
        if (nextUrl) {
            const response = await api.get(nextUrl)
            return response.data;
        }
        const params = {};

        params.limit = DANCE_ATTEMPT_PAGE_LIMIT;
        const response = await api.get(API_ENDPOINTS.video_dance_attempts(video_id), {params})
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}