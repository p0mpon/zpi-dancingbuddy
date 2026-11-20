import {api} from "./axios_instances";
import {API_ENDPOINTS} from "./endpoints";
import {DANCE_ATTEMPT_PAGE_LIMIT, MAIN_PAGE_LIMIT} from "../config/pagination";

export async function getAllVideos({searchQuery, difficulty, nextUrl}) {
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

export const getVideoStream = async (videoId) => {
    const response = await api.get(API_ENDPOINTS.video_stream(videoId), {
        responseType: 'blob',
    });
    return URL.createObjectURL(response.data);
};

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
        formData.append('recording', videoBlob, 'practice_attempt.webm');
        formData.append('mediapipe_data', JSON.stringify(frames));

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
        const response = await api.get(API_ENDPOINTS.dance_attempt_status(taskId));
        return response.data;
    } catch (e) {
        console.error("Failed to fetch score status:", e);
        throw e;
    }
}

export const getDanceAttemptStream = async (attemptId) => {
    const response = await api.get(API_ENDPOINTS.dance_attempt_stream(attemptId), {
        responseType: 'blob',
    });
    return URL.createObjectURL(response.data);
};

export async function editVideo(id, videoData) {
    try {
        const response = await api.patch(API_ENDPOINTS.video_details(id), videoData)
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function publishVideo(id) {
    try {
        const response = await api.patch(API_ENDPOINTS.video_details(id), {
            visibility: 'public'
        });
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function privateVideo(id) {
    try {
        const response = await api.patch(API_ENDPOINTS.video_details(id), {
            visibility: 'private'
        });
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

export async function getMyVideos({searchQuery, difficulty, analysisStatus, visibility, nextUrl}) {
    try {
        if (nextUrl) {
            const response = await api.get(nextUrl)
            return response.data;
        }
        const params = {};

        params.limit = MAIN_PAGE_LIMIT;
        if (searchQuery) params.search = searchQuery;
        if (difficulty) params.difficulty = difficulty;
        if (analysisStatus) params.analysis_status = analysisStatus;
        if (visibility) params.visibility = visibility;

        const response = await api.get(API_ENDPOINTS.my_videos, {params});
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

//--- auth endpoints ---

export async function getCSRFToken(){
    try {
        await api.get(API_ENDPOINTS.csrf);
    } catch (e) {
        console.error("Failed to fetch CSRF token", e);
        throw e;
    }
}

export async function registerUser(userData) {
    try {
        const response = await api.post(API_ENDPOINTS.register, userData);
        return response.data;
    } catch (e) {
        throw e;
    }
}
export async function loginUser(userData) {
    try {
        const response = await api.post(API_ENDPOINTS.login, userData);
        return response.data;
    } catch (e) {
        throw e;
    }
}

export async function logoutUser() {
    try {
        await api.post(API_ENDPOINTS.logout);
    } catch (e) {
        throw e;
    }
}

export async function getUser(nickname) {
    try {
        const response = await api.get(API_ENDPOINTS.public_profile(nickname))
        return response.data;
    } catch (e) {
        if (e.response?.status === 404) {
            return null;
        }

        console.error(`Unexpected error fetching user "${nickname}":`, e);
        throw e;
    }
}

export async function getCurrentUser() {
    try {
        const response = await api.get(API_ENDPOINTS.current_user);
        return response.data;
    } catch (e){
        if (e.response?.status === 401) {
            return null;
        }

        console.error("Failed to fetch current user session:", e);
        return null;
    }
}

export async function getDanceAttemptsForVideo(videoId, nextUrl) {
    if(!videoId && !nextUrl) {
        console.error("You must provide a videoId for video");
        throw "You must provide a videoId for video";
    }
    try {
        if (nextUrl) {
            const response = await api.get(nextUrl)
            return response.data;
        }
        const params = {};

        params.limit = DANCE_ATTEMPT_PAGE_LIMIT;
        params.video_id = videoId;
        const response = await api.get(API_ENDPOINTS.video_dance_attempts, {params})
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function getPastDanceAttempt(attemptId){
    try {
        const response = await api.get(API_ENDPOINTS.retrieve_dance_attempt(attemptId))
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}