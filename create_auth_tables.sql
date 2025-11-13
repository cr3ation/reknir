-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_users_id ON users(id);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

-- Create company_users table
CREATE TABLE IF NOT EXISTS company_users (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'accountant',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    created_by INTEGER REFERENCES users(id),
    CONSTRAINT uq_company_user UNIQUE(company_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_company_users_id ON company_users(id);
CREATE INDEX IF NOT EXISTS ix_company_users_company_id ON company_users(company_id);
CREATE INDEX IF NOT EXISTS ix_company_users_user_id ON company_users(user_id);

-- Verify tables were created
\dt users
\dt company_users
