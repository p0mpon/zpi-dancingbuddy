import React from 'react';
import {Dropdown, Image} from "react-bootstrap";
import {BoxArrowRight, Camera, Person} from "react-bootstrap-icons";
import {useNavigate} from 'react-router-dom';
import {useAuth} from "../../context/AuthContext";
import UserAvatar from "./UserAvatar";

export default function UserMenu() {
    const navigate = useNavigate();
    const {user} = useAuth();
    return (
        <Dropdown align="end">
            <Dropdown.Toggle
                as="div"
                id="user-menu-dropdown"
                style={{cursor: 'pointer'}}
                className="d-flex align-items-center"
            >
                <UserAvatar avatarUrl={user?.avatar_url} size={'38px'} />
            </Dropdown.Toggle>

            <Dropdown.Menu variant="dark" className="shadow border-secondary mt-2">
                {user?.nickname ? <>
                    <Dropdown.Header className="text-muted-light small">
                        Signed in as <br/>
                        <strong className="text-light">{user.nickname}</strong>
                    </Dropdown.Header>
                    <Dropdown.Divider className="border-secondary"/>

                    <Dropdown.Item
                        as="button"
                        type="button"
                        onClick={() => navigate('/account')}
                        className="d-flex align-items-center gap-2">
                        <Person size={16}/>
                        My Account
                    </Dropdown.Item>

                    <Dropdown.Item
                        as="button"
                        type="button"
                        onClick={() => navigate('/my-videos')}
                        className="d-flex align-items-center gap-2">
                        <Camera size={16}/>
                        My Videos
                    </Dropdown.Item>

                    <Dropdown.Divider className="border-secondary"/>

                    <Dropdown.Item
                        as="button"
                        type="button"
                        onClick={() => navigate('/logout')}
                        className="d-flex align-items-center gap-2 text-danger">
                        <BoxArrowRight size={16}/>
                        Logout
                    </Dropdown.Item>
                </> : <>
                    <Dropdown.Header className="text-muted-light small">
                        Not signed in
                    </Dropdown.Header>
                    <Dropdown.Divider className="border-secondary"/>

                    <Dropdown.Item
                        as="button"
                        type="button"
                        onClick={() => navigate('/register')}
                        className="d-flex align-items-center gap-2">
                        <Person size={16}/>
                        Register
                    </Dropdown.Item>

                    <Dropdown.Item
                        as="button"
                        type="button"
                        onClick={() => navigate('/login')}
                        className="d-flex align-items-center gap-2">
                        <Person size={16}/>
                        Login
                    </Dropdown.Item>
                </>
                }
            </Dropdown.Menu>
        </Dropdown>
    )
        ;
}