export const API_ENDPOINTS = {
    // auth
    "csrf": "auth/csrf/",
    "register": "auth/register/",
    "login": "auth/login/",
    "logout": "auth/logout/",
    "password_reset": "auth/password-reset/",

    // user
    "current_user": "users/me/",              // GET, PATCH, DELETE
    "change_login": "users/me/login/",
    "change_password": "users/me/password/",
    "recovery_code": "users/me/recovery-code/",
    "delete_avatar": "users/me/avatar/",               // DELETE
    "public_profile": (nickname) => `users/${nickname}/`,

    // your videos
    "my_videos": "videos/",         //GET, POST
    "my_video_details": (id) => `videos/${id}/`, // GET, PATCH, DELETE
    "reanalysis": (id) => `videos/${id}/reanalyze/`,  // POST
    
    // general videos
    "videos": "library/",                  // GET
    "liked_videos": "library/liked/",
    "like_video": "library/{video_id}/like/",           // PUT, DELETE
    "video_details": (id) => `videos/${id}/`,   // GET
    "video_analysis": (id) => `videos/${id}/analysis/`,     // GET
    "video_stream": (id) => `videos/${id}/stream/`,     // GET
    "video_thumbnail": (id) => `videos/${id}/thumbnail/`,
    
    //dance attempts
    "video_dance_attempts": "dance-attempts/",
    "dance_attempts": "dance-attempts/", // POST
    "dance_attempt_status": (taskId) => `dance-attempts/${taskId}/status/`, // GET
    "retrieve_dance_attempt": (attempt_id) => `dance-attempts/${attempt_id}/`,      //GET, DELETE
    "attempt_reanalysis": (attempt_id) => `dance-attempts/${attempt_id}/reanalyze/`,
    "dance_attempt_stream": (attempt_id) => `dance-attempts/${attempt_id}/stream/`, // GET
    
};