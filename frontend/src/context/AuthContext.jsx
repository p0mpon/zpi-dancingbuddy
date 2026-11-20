
import { createContext, useContext, useState, useEffect } from 'react';
import {getCSRFToken, getCurrentUser, loginUser, logoutUser, registerUser} from "../api/calls";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const initializeApp = async () => {
            try {
                await getCSRFToken();

                const userData = await getCurrentUser();
                setUser(userData);
            } catch (error) {
                console.error("Failed to initialize security context:", error);
            } finally {
                setLoading(false);
            }
        };

        initializeApp();
    }, []);

    const login = async (userData) => {
        // userData = { username: '...', password: '...' }
        await loginUser(userData);

        const current_user = await getCurrentUser();
        setUser(current_user);
    };

    const register = async (userData) => {
        // userData = { nickname: '...', username: '...', password: '...' }

        await registerUser(userData);

        await login({
            username: userData.username,
            password: userData.password
        });
    };

    const logout = async () => {
        try {
            await logoutUser();
        } catch (error) {
            console.error("Logout failed", error);
        } finally {
            setUser(null);
        }
    };

    return (
        <AuthContext.Provider value={{ user, register, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);