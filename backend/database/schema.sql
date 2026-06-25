-- Nexora AI - PostgreSQL Schema Specification
-- Clean Architecture Database DDL with Row Level Security (RLS)

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================================================================
-- 1. SYSTEM ADMINISTRATION & MULTI-TENANCY
-- =========================================================================

CREATE TABLE institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    subdomain VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'pending')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, email)
);
CREATE INDEX idx_users_tenant_email ON users(tenant_id, email);

-- =========================================================================
-- 2. DYNAMIC PERMISSION SYSTEM
-- =========================================================================

CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(255) NOT NULL
);

CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    is_system BOOLEAN DEFAULT FALSE,
    UNIQUE(tenant_id, name)
);

CREATE TABLE role_permissions (
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- =========================================================================
-- 3. ACADEMIC STRUCTURE
-- =========================================================================

CREATE TABLE academic_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT FALSE
);

CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    class_id UUID REFERENCES classes(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    section_id UUID REFERENCES sections(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL
);

-- =========================================================================
-- 4. TIMETABLE MODULE
-- =========================================================================

CREATE TABLE timetable_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    section_id UUID NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    room_number VARCHAR(50)
);
CREATE INDEX idx_timetable_lookup ON timetable_slots(tenant_id, section_id, day_of_week);

-- =========================================================================
-- 5. AI ATTENDANCE & FACE RECOGNITION
-- =========================================================================

CREATE TABLE student_faces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    embedding FLOAT[] NOT NULL,
    image_quality_score FLOAT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending_approval' CHECK (status IN ('pending_approval', 'approved', 'rejected')),
    approved_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE attendance_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    timetable_slot_id UUID REFERENCES timetable_slots(id) ON DELETE SET NULL,
    teacher_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    gps_latitude NUMERIC(9,6),
    gps_longitude NUMERIC(9,6),
    gps_radius_meters INT DEFAULT 50,
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed'))
);

CREATE TABLE attendance_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL CHECK (status IN ('present', 'absent', 'late', 'excused', 'unknown')),
    verification_method VARCHAR(50) NOT NULL CHECK (verification_method IN ('face_auto', 'teacher_manual', 'gps_only')),
    confidence_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, student_id)
);

CREATE TABLE attendance_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    record_id UUID REFERENCES attendance_records(id) ON DELETE CASCADE,
    requested_status VARCHAR(50) NOT NULL CHECK (requested_status IN ('present', 'excused')),
    reason TEXT NOT NULL,
    evidence_url VARCHAR(512),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by UUID REFERENCES users(id),
    review_comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================================
-- 6. AUDIT LOGGING & SECURITY
-- =========================================================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT NOT NULL,
    action VARCHAR(100) NOT NULL,
    previous_value JSONB,
    new_value JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_audit_logs_lookup ON audit_logs(tenant_id, timestamp DESC);

-- =========================================================================
-- 7. ROW-LEVEL SECURITY (RLS) POLICIES
-- =========================================================================

-- Enable RLS on multi-tenant tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE academic_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE timetable_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_faces ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_corrections ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Helper function to fetch current tenant from transaction settings context
CREATE OR REPLACE FUNCTION get_current_tenant() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_tenant', true), '')::UUID;
$$ LANGUAGE sql STABLE;

-- Apply Tenant Isolation Policies (preventing cross-tenant leaks)
CREATE POLICY tenant_isolation_policy ON users FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON roles FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON academic_sessions FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON departments FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON courses FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON classes FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON sections FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON subjects FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON timetable_slots FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON student_faces FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON attendance_sessions FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON attendance_records FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON attendance_corrections FOR ALL USING (tenant_id = get_current_tenant());
CREATE POLICY tenant_isolation_policy ON audit_logs FOR ALL USING (tenant_id = get_current_tenant());
