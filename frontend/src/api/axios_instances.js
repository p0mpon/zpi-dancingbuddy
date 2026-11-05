import axios from "axios";


export const defaultApi = axios.create({
    baseURL: `${process.env.REACT_APP_API_URL}/api/`,
    withCredentials: true,
    timeout: 5000,
    xsrfCookieName: 'csrftoken',
    xsrfHeaderName: 'X-CSRFToken',
    auth: {
        username: process.env.REACT_APP_USERNAME,
        password: process.env.REACT_APP_PASSWORD
    }
});

export const authApi = axios.create({
    baseURL: `${process.env.REACT_APP_API_URL}/api-auth/`,
    withCredentials: true,
    xsrfCookieName: 'csrftoken',
    xsrfHeaderName: 'X-CSRFToken',
});