import React, { useState } from 'react';
import { Container, Card, Form, Button, Alert } from 'react-bootstrap';
import {Link, useNavigate} from 'react-router-dom';
import {useAuth} from "../../context/AuthContext";

export default function RegisterPage() {

    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
        confirmPassword: ''
    });
    const [error, setError] = useState('');

    const {register} = useAuth();
    const navigate = useNavigate();

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        const { username, email, password, confirmPassword } = formData;

        if (!username || !email || !password || !confirmPassword) {
            setError('Please fill in all fields.');
            return;
        }

        if (password !== confirmPassword) {
            setError('Passwords do not match.');
        }
        try {
            await register({ email, password });
            navigate('/');
        } catch (err) {
            setError("Login invalid");
        }
    };

    return (
        <Container className="d-flex align-items-center justify-content-center py-5">
            <Card bg="black" text="light" className="border-secondary shadow p-3" style={{ maxWidth: '440px', width: '100%' }}>
                <Card.Body>
                    <div className="text-center mb-4">
                        <h3 className="fw-bold">Create Account</h3>
                    </div>

                    {error && <Alert variant="danger" className="py-2 small">{error}</Alert>}

                    <Form onSubmit={handleSubmit}>
                        <Form.Group className="mb-3" controlId="regusername">
                            <Form.Label className="text-muted-light small" column>Username</Form.Label>
                            <Form.Control
                                type="text"
                                name="username"
                                placeholder="Alex_Dev"
                                value={formData.username}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Form.Group className="mb-3" controlId="regEmail">
                            <Form.Label className="text-muted-light small" column>Email Address</Form.Label>
                            <Form.Control
                                type="email"
                                name="email"
                                placeholder="name@example.com"
                                value={formData.email}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Form.Group className="mb-3" controlId="regPassword">
                            <Form.Label className="text-muted-light small" column>Password</Form.Label>
                            <Form.Control
                                type="password"
                                name="password"
                                placeholder="••••••••"
                                value={formData.password}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Form.Group className="mb-4" controlId="regConfirmPassword">
                            <Form.Label className="text-muted-light small" column>Confirm Password</Form.Label>
                            <Form.Control
                                type="password"
                                name="confirmPassword"
                                placeholder="••••••••"
                                value={formData.confirmPassword}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Button variant="primary" type="submit" className="w-100 fw-bold py-2 mb-3">
                            Create Account
                        </Button>
                    </Form>

                    <div className="text-center text-muted-light small">
                        Already have an account?{' '}
                        <Link to="/login" className="text-primary text-decoration-none fw-semibold">
                            Sign In
                        </Link>
                    </div>
                </Card.Body>
            </Card>
        </Container>
    );
}