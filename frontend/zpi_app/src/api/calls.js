import {defaultApi} from "./axios_instances";
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
        console.error(e);
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

