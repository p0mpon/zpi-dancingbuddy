// import axios from "axios";
//
// export const defaultApi = axios.create({
//     baseURL: `${process.env.REACT_APP_API_URL}/api/`,
//     timeout: 5000,
//     headers: { "X-Custom-Header": "foobar" },
// });
//
// export const authApi = axios.create({
//     baseURL: `${process.env.REACT_APP_API_URL}/api/auth/`,
//     withCredentials: true,
//     xsrfCookieName: 'csrftoken',
//     xsrfHeaderName: 'X-CSRFToken',
// });

//to pod spodem będzie do wywalenia jak będą endpointy do atakowania

import axios from "axios";

const USE_MOCK = true;

const getStoredMockState = () => {
    const saved = localStorage.getItem('mock_app_state');
    if (saved) {
        try {
            return JSON.parse(saved);
        } catch (e) {
        }
    }
    return {
        isAuthenticated: false,
        user: {
            id: 1,
            username: 'testuser',
            email: 'test@example.com',
            avatar: "https://placehold.co/150x150/3b82f6/ffffff?text=Alex"
        },
        videos: [
            { id: 1, title: 'Video 1', description: 'twoja stara.', author: 'abc', url: '/test_videos/bst.mp4' },
            { id: 2, title: 'Video 2', description: 'twoja stara', author: 'jpg', url: '/test_videos/bst.mp4' }
        ]
    };
};

const saveMockState = (state) => {
    localStorage.setItem('mock_app_state', JSON.stringify(state));
};

let mockState = getStoredMockState();

export const defaultApi = axios.create({
    baseURL: `${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/`,
    timeout: 5000,
    headers: { "X-Custom-Header": "foobar" },
});

export const authApi = axios.create({
    baseURL: `${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/auth/`,
    withCredentials: true,
    xsrfCookieName: 'csrftoken',
    xsrfHeaderName: 'X-CSRFToken',
});

if (USE_MOCK) {
    const attachMockInterceptor = (instance) => {
        instance.interceptors.request.use(async (config) => {
            await new Promise((resolve) => setTimeout(resolve, 300));
            const url = config.url || '';
            const method = (config.method || 'get').toLowerCase();

            let parsedData = {};
            if (config.data) {
                try {
                    parsedData = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
                } catch (e) {
                    parsedData = {};
                }
            }

            const createMockResponse = (status, data, headers = {}) => ({
                ...config,
                adapter: () => Promise.resolve({ data, status, statusText: status >= 200 && status < 300 ? 'OK' : 'Error', headers, config }),
            });

            if (url.includes('login/') && method === 'post') {
                if (parsedData.email && parsedData.password) {
                    mockState.isAuthenticated = true;
                    saveMockState(mockState);
                    return createMockResponse(200, { detail: 'Successfully logged in' }, { 'set-cookie': 'sessionid=mock-session-456' });
                }
                return createMockResponse(400, { non_field_errors: ['Invalid credentials'] });
            }
            if (url.includes('user/') && method === 'get') {
                mockState = getStoredMockState();
                if (!mockState.isAuthenticated) {
                    return createMockResponse(204, { detail: 'No user is logged in.' });
                }
                return createMockResponse(200, mockState.user);
            }
            if (url.includes('logout/') && method === 'post') {
                mockState.isAuthenticated = false;
                saveMockState(mockState);
                return createMockResponse(200, { detail: 'Successfully logged out' });
            }

            const isVideosList = url.match(/videos\/?$/);
            const videoDetailMatch = url.match(/videos\/(\d+)\/?$/);

            if (isVideosList && method === 'get') {
                mockState = getStoredMockState();
                return createMockResponse(200, mockState.videos);
            }

            if (isVideosList && method === 'post') {
                mockState = getStoredMockState();
                let title = 'Untitled Video';
                let description = '';
                let author = '';
                let videoUrl = '/videos/bst.mp4';

                if (config.data instanceof FormData) {
                    title = config.data.get('title') || title;
                    description = config.data.get('description') || description;
                    author = config.data.get('author') || author;

                    const file = config.data.get('video') || config.data.get('file');
                    if (file instanceof File) {
                        videoUrl = URL.createObjectURL(file);
                    }
                } else {
                    title = parsedData.title || title;
                    description = parsedData.description || description;
                    author = parsedData.author || author;
                    videoUrl = parsedData.url || videoUrl;
                }

                const newVideo = {
                    id: mockState.videos.length > 0 ? Math.max(...mockState.videos.map(v => v.id)) + 1 : 1,
                    title,
                    description,
                    author,
                    url: videoUrl,
                    ...parsedData
                };
                mockState.videos.push(newVideo);
                saveMockState(mockState);
                return createMockResponse(201, newVideo);
            }

            if (videoDetailMatch) {
                const videoId = parseInt(videoDetailMatch[1], 10);
                mockState = getStoredMockState();
                const videoIndex = mockState.videos.findIndex(v => v.id === videoId);

                if (videoIndex === -1) {
                    return createMockResponse(404, { detail: 'Not found.' });
                }

                if (method === 'get') {
                    return createMockResponse(200, mockState.videos[videoIndex]);
                }

                if (method === 'patch') {
                    mockState.videos[videoIndex] = {
                        ...mockState.videos[videoIndex],
                        ...parsedData
                    };
                    saveMockState(mockState);
                    return createMockResponse(200, mockState.videos[videoIndex]);
                }

                if (method === 'delete') {
                    mockState.videos.splice(videoIndex, 1);
                    saveMockState(mockState);
                    return createMockResponse(204, null);
                }
            }

            return config;
        });
    };

    attachMockInterceptor(defaultApi);
    attachMockInterceptor(authApi);
}