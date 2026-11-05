import {Navigate} from "react-router-dom";
import {useEffect} from "react";
import {useAuth} from "../../context/AuthContext";

export function Logout() {
    const {logout} = useAuth();
    useEffect(() => {
        const fetchData = async () => {
            try {
                await logout();
            } catch (error) {
                console.log(error);
            }
        }
        fetchData();
    }, [])
    return (
        <Navigate to={'/'}></Navigate>
    )
}