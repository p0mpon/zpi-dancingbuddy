import {authApi, defaultApi} from "./axios_instances";
import {API_ENDPOINTS} from "./endpoints";

export async function getAllVideos(){
    try {
        const response = await defaultApi.get(API_ENDPOINTS.videos)
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function postVideo(video){
    try {
        const response = await defaultApi.post(API_ENDPOINTS.videos, video)
        return response.data;
    } catch (e) {
        console.error("error details:", e.response?.data);
        throw e;
    }
}

export async function getVideo(id){
    try {
        const response = await defaultApi.get(API_ENDPOINTS.video_details(id))
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function getFullVideo(id){
    try {
        const response = await defaultApi.get(API_ENDPOINTS.video_details(id))
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

export async function editVideo(id, videoData){
    try {
        const response = await defaultApi.put(API_ENDPOINTS.video_details(id, videoData))
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

export async function deleteVideo(id){
    try {
        const response = await defaultApi.delete(API_ENDPOINTS.video_details(id))
        return response.data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

//--- auth endpoints ---

export async function loginUser (username, password) {
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

export async function getUser(id){
    try {
        const response = await authApi.get(API_ENDPOINTS.user)
        return response.data;
    } catch (error){
        return false;
    }
}

