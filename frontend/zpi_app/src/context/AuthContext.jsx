
import { createContext, useContext, useState, useEffect } from 'react';
import {getUser, loginUser} from "../api/calls";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const checkAuth = async () => {
            try {
                const userData = await getUser();
                if (userData) {
                    setUser(userData);
                }
            } catch (error) {
                setUser(null);
            } finally {
                setLoading(false);
            }
        };

        checkAuth();
    }, []);

    const login = async (username, password) => {
        const userData = await loginUser(username, password);
        if (userData) {
            setUser(userData);
            return true;
        }
        return false;
    };

    const logout = async () => {
        try {
            setUser(null);
        } catch (error) {
            console.error("Logout failed", error);
        }
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);