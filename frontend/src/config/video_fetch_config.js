import {getFullLibraryVideo, getLibraryVideoDetails, getMyFullVideo, getMyVideoDetails} from "../api/calls";

export const VIDEO_FETCH_CONFIGS = {
    general: {
        getVideoDetails: (id) => getLibraryVideoDetails(id),
        getFullVideo: (id) => getFullLibraryVideo(id),
    },
    user_specific: {
        getVideoDetails: (id) => getMyVideoDetails(id),
        getFullVideo: (id) => getMyFullVideo(id),
    }
}