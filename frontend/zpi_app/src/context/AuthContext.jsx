
import { createContext, useContext, useState, useEffect } from 'react';
import {authApi} from '../api/axios_instances';
import {API_ENDPOINTS} from "../api/endpoints";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        authApi.get(API_ENDPOINTS.user)
            .then((response) => {
                console.log(response);
                setUser(response.data)
            })
            // .catch(() => setUser(null))
            .finally(() => setLoading(false));
    }, []);

    const login = async (credentials) => {
        await authApi.post(API_ENDPOINTS.login, credentials);
        const response = await authApi.get(API_ENDPOINTS.user);
        setUser(response.data);
    };

    const logout = async () => {
        await authApi.post(API_ENDPOINTS.logout);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);