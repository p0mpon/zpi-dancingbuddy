import axios from "axios";
import {API_ENDPOINTS} from "./endpoints";

export const api = axios.create({
    baseURL: `${process.env.REACT_APP_API_URL}/api/`,
    withCredentials: true,
    withXSRFToken: true,
    timeout: 5000,
    xsrfCookieName: 'csrftoken',
    xsrfHeaderName: 'X-CSRFToken',
});

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        console.log(originalRequest);

        if (error.response?.status === 401) {
            const ignoredEndpoints = originalRequest.url.includes(API_ENDPOINTS.login) ||
                originalRequest.url.includes(API_ENDPOINTS.register) ||
                originalRequest.url.includes(API_ENDPOINTS.csrf) ||
                originalRequest.url.includes(API_ENDPOINTS.current_user)||
                originalRequest.url.includes(API_ENDPOINTS.logout);

            if (!ignoredEndpoints) {
                window.location.href = '/login';
            }
        }

        return Promise.reject(error);
    }
);