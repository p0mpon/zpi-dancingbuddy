export const API_ENDPOINTS = {
    "register": "register/",
    "login": "login/",
    "logout": "logout/",
    "user": "user/",

    "videos": "videos/",                  // GET, POST
    "video_details": (id) => `videos/${id}/`, // GET, PATCH, DELETE
    "video_analysis": (id) => `videos/${id}/analysis/`, // GET
};