import axios from "axios";


export const api = axios.create({
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

axios.interceptors.response.use(
    (response) => response,
    async (error) => {
        if (error.response && (error.response?.data?.error_code === 'TOKEN_EXPIRED')) {
            localStorage.removeItem('csrftoken');
            window.location.href = '/';
        }
        return Promise.reject(error);
    }
);