import React from 'react';
import {Dropdown, Image} from "react-bootstrap";
import {BoxArrowRight, Person} from "react-bootstrap-icons";
import {useAuth} from "../../context/AuthContext";

export default function UserMenu() {
    const {user} = useAuth();
    return (
        <Dropdown align="end">
            <Dropdown.Toggle
                as="div"
                id="user-menu-dropdown"
                style={{cursor: 'pointer'}}
                className="d-flex align-items-center"
            >
                <div
                    className="rounded-circle bg-secondary border border-secondary overflow-hidden d-flex align-items-center justify-content-center shadow-sm"
                    style={{width: '38px', height: '38px'}}
                >
                    <Image
                        src={user?.avatar ? user?.avatar : "https://placehold.co/100x100/3b82f6/ffffff?text=NA"}
                        alt="User Avatar"
                        fluid
                    />
                </div>
            </Dropdown.Toggle>

            <Dropdown.Menu variant="dark" className="shadow border-secondary mt-2">
                {user?.username ? <>
                    <Dropdown.Header className="text-muted-light small">
                        Signed in as <br/>
                        <strong className="text-light">{user.username}</strong>
                    </Dropdown.Header>
                    <Dropdown.Divider className="border-secondary"/>

                    <Dropdown.Item href="account" className="d-flex align-items-center gap-2">
                        <Person size={16}/>
                        My Account
                    </Dropdown.Item>

                    <Dropdown.Divider className="border-secondary"/>

                    <Dropdown.Item href="logout" className="d-flex align-items-center gap-2 text-danger">
                        <BoxArrowRight size={16}/>
                        Logout
                    </Dropdown.Item>
                </> : <>
                    <Dropdown.Header className="text-muted-light small">
                        Not signed in
                    </Dropdown.Header>
                    <Dropdown.Divider className="border-secondary"/>

                    <Dropdown.Item href="register" className="d-flex align-items-center gap-2">
                        <Person size={16}/>
                        Register
                    </Dropdown.Item>

                    <Dropdown.Item href="login" className="d-flex align-items-center gap-2">
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