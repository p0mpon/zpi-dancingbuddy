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
        console.log(process.env.REACT_APP_API_URL)
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