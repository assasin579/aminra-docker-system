--
-- PostgreSQL database dump
--

\restrict NotxvhnJ3QRiIiQ5FFZusNJGqUSFiCoqYtoGg2DFieit2T0i9ZxmW1FGOu7hx0A

-- Dumped from database version 15.19
-- Dumped by pg_dump version 15.19

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: batch_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.batch_status AS ENUM (
    'draft',
    'in_progress',
    'completed',
    'rejected'
);


--
-- Name: document_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.document_status AS ENUM (
    'uploaded',
    'reviewing',
    'approved',
    'rejected',
    'evaluating'
);


--
-- Name: material_risk; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.material_risk AS ENUM (
    'safe',
    'requires_cert',
    'prohibited',
    'unknown'
);


--
-- Name: supplier_certificate_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.supplier_certificate_status AS ENUM (
    'active',
    'expired',
    'suspended',
    'revoked',
    'pending_review'
);


--
-- Name: supplier_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.supplier_status AS ENUM (
    'pending',
    'verified',
    'expired',
    'suspended'
);


--
-- Name: user_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role AS ENUM (
    'business',
    'provider'
);


--
-- Name: user_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_status AS ENUM (
    'pending',
    'active',
    'suspended'
);


--
-- Name: audit_logs_immutable_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.audit_logs_immutable_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only; UPDATE/DELETE not permitted (op=%)', TG_OP;
        END;
        $$;


--
-- Name: block_delete_with_children(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.block_delete_with_children() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
          child_count INT;
        BEGIN
          SELECT COUNT(*) INTO child_count
            FROM documents WHERE version_parent_id = OLD.id;
          IF child_count > 0 THEN
            RAISE EXCEPTION
              'Cannot delete document % — has % child version(s). Use supersede or delete children first',
              OLD.id, child_count
              USING ERRCODE = '23503',
                    HINT    = 'POST /api/documents/{id}/supersede';
          END IF;
          RETURN OLD;
        END;
        $$;


--
-- Name: enforce_documents_chain_tenant(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.enforce_documents_chain_tenant() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
          IF NEW.version_parent_id IS NOT NULL THEN
            IF NOT EXISTS (
              SELECT 1 FROM documents
              WHERE id = NEW.version_parent_id AND tenant_id = NEW.tenant_id
            ) THEN
              RAISE EXCEPTION
                'version_parent_id (%) must reference document in same tenant (%)',
                NEW.version_parent_id, NEW.tenant_id
                USING ERRCODE = '23514';
            END IF;
          END IF;

          IF NEW.superseded_by_id IS NOT NULL THEN
            IF NOT EXISTS (
              SELECT 1 FROM documents
              WHERE id = NEW.superseded_by_id AND tenant_id = NEW.tenant_id
            ) THEN
              RAISE EXCEPTION
                'superseded_by_id (%) must reference document in same tenant (%)',
                NEW.superseded_by_id, NEW.tenant_id
                USING ERRCODE = '23514';
            END IF;
          END IF;

          IF NEW.approval_status = 'approved' AND NEW.approved_at IS NOT NULL
             AND (TG_OP = 'INSERT' OR OLD.approval_status IS DISTINCT FROM 'approved') THEN
            NEW.retention_expires_at := COALESCE(NEW.effective_date::TIMESTAMPTZ, NEW.approved_at)
                                      + (NEW.retention_period_days || ' days')::INTERVAL;
          END IF;

          IF NEW.superseded_by_id IS NOT NULL
             AND (TG_OP = 'INSERT' OR OLD.superseded_by_id IS NULL) THEN
            NEW.approval_status := 'obsolete';
          END IF;

          RETURN NEW;
        END;
        $$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_checklist_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_checklist_templates (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    provider_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    standard character varying(100),
    items jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid,
    action character varying(100) NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id uuid,
    created_at timestamp with time zone DEFAULT now(),
    user_email character varying(255),
    user_role character varying(50),
    tenant_id uuid,
    changes jsonb,
    metadata jsonb DEFAULT '{}'::jsonb
);


--
-- Name: audit_ncr; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_ncr (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    visit_id uuid NOT NULL,
    item_id uuid,
    description text NOT NULL,
    severity character varying(20) NOT NULL,
    photo_paths jsonb DEFAULT '[]'::jsonb,
    corrective_action text,
    deadline date,
    status character varying(20) DEFAULT 'open'::character varying,
    evidence_paths jsonb DEFAULT '[]'::jsonb,
    closed_at timestamp with time zone,
    closed_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT audit_ncr_severity_check CHECK (((severity)::text = ANY ((ARRAY['critical'::character varying, 'major'::character varying, 'minor'::character varying])::text[]))),
    CONSTRAINT audit_ncr_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'in_review'::character varying, 'closed'::character varying])::text[])))
);


--
-- Name: audit_visit_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_visit_items (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    visit_id uuid NOT NULL,
    code character varying(20),
    category character varying(255) NOT NULL,
    criteria text NOT NULL,
    severity character varying(20) NOT NULL,
    result character varying(20),
    clause text,
    audit_method text,
    documents text,
    evidence text,
    corrective_action text,
    corrective_status character varying(20),
    note text,
    photo_paths jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT audit_visit_items_corrective_status_check CHECK (((corrective_status)::text = ANY ((ARRAY['pending'::character varying, 'in_progress'::character varying, 'completed'::character varying])::text[]))),
    CONSTRAINT audit_visit_items_result_check CHECK (((result)::text = ANY ((ARRAY['conform'::character varying, 'minor_nc'::character varying, 'major_nc'::character varying, 'na'::character varying, 'observation'::character varying])::text[]))),
    CONSTRAINT audit_visit_items_severity_check CHECK (((severity)::text = ANY ((ARRAY['critical'::character varying, 'major'::character varying, 'minor'::character varying])::text[])))
);


--
-- Name: audit_visits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_visits (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    business_tenant uuid NOT NULL,
    provider_id uuid NOT NULL,
    auditor_id uuid,
    template_id uuid,
    visit_type character varying(20) NOT NULL,
    status character varying(30) DEFAULT 'scheduled'::character varying,
    scheduled_date date NOT NULL,
    location text,
    notes text,
    auditor_signature_path text,
    business_signature_path text,
    start_gps jsonb,
    end_gps jsonb,
    report_pdf_path text,
    compliance_score integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT audit_visits_compliance_score_check CHECK (((compliance_score >= 0) AND (compliance_score <= 100))),
    CONSTRAINT audit_visits_status_check CHECK (((status)::text = ANY ((ARRAY['scheduled'::character varying, 'in_progress'::character varying, 'completed'::character varying, 'report_submitted'::character varying])::text[]))),
    CONSTRAINT audit_visits_visit_type_check CHECK (((visit_type)::text = ANY ((ARRAY['initial'::character varying, 'renewal'::character varying, 'surprise'::character varying])::text[])))
);


--
-- Name: batch_anchor_proofs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.batch_anchor_proofs (
    batch_id uuid NOT NULL,
    anchor_id uuid NOT NULL,
    leaf_hash character varying(66) NOT NULL,
    leaf_index integer NOT NULL,
    proof_path jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: batch_materials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.batch_materials (
    batch_id uuid NOT NULL,
    material_id uuid NOT NULL,
    quantity numeric(12,3),
    unit character varying(50),
    supplier_id uuid,
    eligibility_id uuid,
    eligibility_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: batch_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.batch_steps (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    batch_id uuid NOT NULL,
    node_id character varying(100) NOT NULL,
    step_name character varying(255) NOT NULL,
    performed_by character varying(255),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    status character varying(50) DEFAULT 'pending'::character varying,
    notes text,
    photo_path text,
    checklist jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    step_hash text,
    approved_by character varying(255),
    approved_at timestamp with time zone
);


--
-- Name: blockchain_anchors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.blockchain_anchors (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    chain character varying(20) NOT NULL,
    merkle_root character varying(66) NOT NULL,
    tx_hash character varying(128),
    block_number bigint,
    cert_count integer DEFAULT 0 NOT NULL,
    batch_count integer DEFAULT 0 NOT NULL,
    submitted_at timestamp with time zone DEFAULT now() NOT NULL,
    confirmed_at timestamp with time zone,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    parent_anchor uuid,
    metadata jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT chk_anchor_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'submitted'::character varying, 'confirmed'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: cert_anchor_proofs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cert_anchor_proofs (
    cert_id uuid NOT NULL,
    anchor_id uuid NOT NULL,
    leaf_hash character varying(66) NOT NULL,
    leaf_index integer NOT NULL,
    proof_path jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: certificate_risk_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certificate_risk_alerts (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    impacted_tenant_id uuid NOT NULL,
    supplier_id uuid NOT NULL,
    certificate_id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    severity character varying(20) DEFAULT 'high'::character varying NOT NULL,
    message text NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT certificate_risk_alerts_severity_check CHECK (((severity)::text = ANY ((ARRAY['info'::character varying, 'medium'::character varying, 'high'::character varying, 'critical'::character varying])::text[]))),
    CONSTRAINT certificate_risk_alerts_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'acknowledged'::character varying, 'resolved'::character varying])::text[])))
);


--
-- Name: custom_placeholders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.custom_placeholders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    key character varying(100) NOT NULL,
    label character varying(200) NOT NULL,
    description text,
    default_value text,
    source character varying(200),
    is_system boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: deletion_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deletion_tokens (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    token character varying(255) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    confirmed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    filename character varying(255) NOT NULL,
    original_filename character varying(255) NOT NULL,
    file_path text,
    file_size bigint,
    mime_type character varying(100),
    user_id uuid,
    tenant_id uuid NOT NULL,
    doc_type character varying(100),
    status public.document_status DEFAULT 'uploaded'::public.document_status,
    compliance_score integer,
    evaluation_result jsonb,
    uploaded_at timestamp with time zone DEFAULT now(),
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    review_notes text,
    cb_approved_at timestamp with time zone,
    version_number integer DEFAULT 1 NOT NULL,
    version_parent_id uuid,
    approver_id uuid,
    approved_at timestamp with time zone,
    effective_date date,
    next_review_date date,
    retention_period_days integer DEFAULT 1825 NOT NULL,
    retention_expires_at timestamp with time zone,
    superseded_by_id uuid,
    approval_status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    dossier_id uuid,
    CONSTRAINT documents_approval_status_check CHECK (((approval_status)::text = ANY ((ARRAY['draft'::character varying, 'pending_approval'::character varying, 'approved'::character varying, 'obsolete'::character varying])::text[]))),
    CONSTRAINT documents_compliance_score_check CHECK (((compliance_score >= 0) AND (compliance_score <= 100))),
    CONSTRAINT documents_retention_period_days_check CHECK ((retention_period_days >= 1825))
);


--
-- Name: dossiers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dossiers (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    standard_type_id uuid,
    title character varying(255) NOT NULL,
    status character varying(50) DEFAULT 'draft'::character varying NOT NULL,
    notes text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: feature_flags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feature_flags (
    name character varying(64) NOT NULL,
    description text,
    default_enabled boolean DEFAULT false NOT NULL,
    rollout_percentage integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT feature_flags_rollout_percentage_check CHECK (((rollout_percentage >= 0) AND (rollout_percentage <= 100)))
);


--
-- Name: halal_certificates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.halal_certificates (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    submission_id uuid NOT NULL,
    cert_number character varying(100) NOT NULL,
    issued_by uuid NOT NULL,
    business_tenant uuid NOT NULL,
    company_name character varying(255),
    issue_date date DEFAULT CURRENT_DATE NOT NULL,
    expiry_date date NOT NULL,
    pdf_path text,
    status character varying(50) DEFAULT 'active'::character varying,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    revocation_reason text,
    revoked_at timestamp with time zone,
    revoked_by uuid,
    expiry_alerts_sent jsonb DEFAULT '[]'::jsonb NOT NULL,
    CONSTRAINT chk_cert_revocation_has_reason CHECK (((revoked_at IS NULL) OR ((revocation_reason IS NOT NULL) AND (revoked_by IS NOT NULL))))
);


--
-- Name: industry_schemas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.industry_schemas (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    code character varying(50) NOT NULL,
    name_vi character varying(255) NOT NULL,
    name_en character varying(255),
    description text,
    jakim_scheme character varying(100),
    icon character varying(50),
    enabled boolean DEFAULT true NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid
);


--
-- Name: COLUMN industry_schemas.jakim_scheme; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.industry_schemas.jakim_scheme IS 'DEPRECATED 2026-05-10: scheme info moved to standard_types. See industry_standards M:N mapping.';


--
-- Name: industry_standards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.industry_standards (
    industry_schema_id uuid NOT NULL,
    standard_type_id uuid NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    display_order integer DEFAULT 0 NOT NULL
);


--
-- Name: materials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.materials (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    supplier_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    sku character varying(100),
    category character varying(100),
    halal_risk public.material_risk DEFAULT 'unknown'::public.material_risk,
    description text,
    unit character varying(50),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: member_invites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.member_invites (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    email character varying(255) NOT NULL,
    invite_token character varying(255) NOT NULL,
    role character varying(100),
    department character varying(255),
    expires_at timestamp with time zone NOT NULL,
    accepted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    type character varying(50) NOT NULL,
    title character varying(255) NOT NULL,
    message text,
    read boolean DEFAULT false,
    link text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: ops_user_link_backup_20260909; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ops_user_link_backup_20260909 (
    backed_up_at timestamp with time zone,
    id uuid,
    email character varying(255),
    role public.user_role,
    company_name character varying(255),
    company_code character varying(100),
    status public.user_status,
    tenant_id uuid,
    is_owner boolean,
    invited_by uuid,
    ihc_role character varying(100),
    department character varying(255),
    approved_by uuid,
    approved_at timestamp with time zone,
    rejection_reason text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    address text,
    phone character varying(50),
    representative_name character varying(255),
    deleted_at timestamp with time zone,
    manager_name character varying(255),
    permissions jsonb,
    notify_eval_done boolean,
    notify_submission_reply boolean,
    industry_schema_id uuid,
    keycloak_sub uuid
);


--
-- Name: process_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.process_templates (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    flowchart jsonb DEFAULT '{"edges": [], "nodes": []}'::jsonb NOT NULL,
    version integer DEFAULT 1,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: production_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.production_batches (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    batch_code character varying(100) NOT NULL,
    product_name character varying(255) NOT NULL,
    process_template_id uuid,
    status public.batch_status DEFAULT 'draft'::public.batch_status,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    compliance_score integer,
    qr_code_url text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    integrity_hash text,
    sealed_data jsonb,
    assigned_to uuid,
    assigned_name character varying(255),
    approved_by character varying(255),
    approved_at timestamp with time zone,
    public_trace_id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    public_trace_enabled boolean DEFAULT false NOT NULL
);


--
-- Name: push_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_subscriptions (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    user_id uuid NOT NULL,
    endpoint text NOT NULL,
    p256dh text NOT NULL,
    auth text NOT NULL,
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: schema_doc_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_doc_types (
    schema_id uuid NOT NULL,
    doc_type character varying(100) NOT NULL,
    required boolean DEFAULT true NOT NULL,
    display_order integer DEFAULT 0 NOT NULL
);


--
-- Name: standard_doc_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.standard_doc_types (
    standard_type_id uuid NOT NULL,
    doc_type character varying(100) NOT NULL,
    required boolean DEFAULT true NOT NULL,
    display_order integer DEFAULT 0 NOT NULL
);


--
-- Name: standard_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.standard_types (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    code character varying(50) NOT NULL,
    name_vi character varying(255) NOT NULL,
    name_en character varying(255),
    organization character varying(100),
    scheme_version character varying(50),
    description text,
    full_text_url text,
    enabled boolean DEFAULT true NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid
);


--
-- Name: submission_comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submission_comments (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    submission_id uuid NOT NULL,
    author_id uuid NOT NULL,
    author_role character varying(20) NOT NULL,
    author_name character varying(255) NOT NULL,
    message text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: submission_evaluations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submission_evaluations (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    submission_id uuid NOT NULL,
    auditor_id uuid NOT NULL,
    checklist jsonb DEFAULT '[]'::jsonb NOT NULL,
    score integer,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT submission_evaluations_score_check CHECK (((score >= 0) AND (score <= 100)))
);


--
-- Name: submission_revision_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submission_revision_requests (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    submission_id uuid NOT NULL,
    round integer NOT NULL,
    requester_id uuid NOT NULL,
    requester_name character varying(255) NOT NULL,
    feedback text NOT NULL,
    document_feedback jsonb DEFAULT '[]'::jsonb,
    requested_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    business_response text
);


--
-- Name: submissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.submissions (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    business_tenant uuid NOT NULL,
    provider_id uuid NOT NULL,
    auditor_id uuid,
    document_ids uuid[] DEFAULT '{}'::uuid[] NOT NULL,
    status character varying(50) DEFAULT 'pending'::character varying,
    notes text,
    auditor_notes text,
    submitted_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    company_name character varying(255),
    deadline timestamp with time zone,
    revision_round integer DEFAULT 0 NOT NULL,
    revision_requested_at timestamp with time zone,
    revision_resubmitted_at timestamp with time zone,
    sla_alerts_sent jsonb DEFAULT '[]'::jsonb NOT NULL,
    archived_at timestamp with time zone,
    CONSTRAINT chk_submission_status_enum CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'assigned'::character varying, 'reviewing'::character varying, 'revision_required'::character varying, 'returned'::character varying, 'rejected'::character varying, 'approved'::character varying])::text[])))
);


--
-- Name: supplier_certificates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supplier_certificates (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    supplier_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    cert_type character varying(100),
    cert_number character varying(255),
    issuing_body character varying(255),
    issued_date date,
    expiry_date date,
    file_path text,
    original_filename character varying(255),
    file_size bigint,
    created_at timestamp with time zone DEFAULT now(),
    uploaded_by character varying(50)
);


--
-- Name: supplier_eligibilities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supplier_eligibilities (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    supplier_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    certificate_no character varying(255) NOT NULL,
    issuer_name character varying(255) NOT NULL,
    status public.supplier_certificate_status DEFAULT 'pending_review'::public.supplier_certificate_status NOT NULL,
    valid_from date NOT NULL,
    valid_until date NOT NULL,
    scope jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_of_truth character varying(50) DEFAULT 'cb'::character varying NOT NULL,
    changed_at timestamp with time zone DEFAULT now(),
    changed_by uuid,
    reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    provider_id uuid,
    source_certificate_id uuid,
    CONSTRAINT supplier_eligibilities_scope_object_check CHECK ((jsonb_typeof(scope) = 'object'::text)),
    CONSTRAINT supplier_eligibilities_valid_range_check CHECK ((valid_until >= valid_from))
);


--
-- Name: suppliers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.suppliers (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    address text,
    phone character varying(50),
    email character varying(255),
    contact_person character varying(255),
    supplier_type character varying(100),
    status public.supplier_status DEFAULT 'pending'::public.supplier_status,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    tax_code character varying(20),
    invite_token character varying(255),
    invite_expires_at timestamp with time zone
);


--
-- Name: supply_relationships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supply_relationships (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    buyer_tenant_id uuid NOT NULL,
    supplier_tenant_id uuid,
    supplier_id uuid NOT NULL,
    material_category character varying(100),
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    last_purchase_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT supply_relationships_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'paused'::character varying, 'ended'::character varying])::text[])))
);


--
-- Name: tenant_feature_overrides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_feature_overrides (
    tenant_id uuid NOT NULL,
    feature_name character varying(64) NOT NULL,
    enabled boolean NOT NULL,
    override_reason text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    email character varying(255) NOT NULL,
    role public.user_role NOT NULL,
    company_name character varying(255) NOT NULL,
    company_code character varying(100),
    status public.user_status DEFAULT 'pending'::public.user_status,
    tenant_id uuid,
    is_owner boolean DEFAULT true,
    invited_by uuid,
    ihc_role character varying(100),
    department character varying(255),
    approved_by uuid,
    approved_at timestamp with time zone,
    rejection_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    address text,
    phone character varying(50),
    representative_name character varying(255),
    deleted_at timestamp with time zone,
    manager_name character varying(255),
    permissions jsonb DEFAULT '{}'::jsonb,
    notify_eval_done boolean DEFAULT true,
    notify_submission_reply boolean DEFAULT true,
    industry_schema_id uuid,
    keycloak_sub uuid
);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
040_public_trace_id
\.


--
-- Data for Name: audit_checklist_templates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_checklist_templates (id, provider_id, name, standard, items, created_at, updated_at) FROM stdin;
81653e91-6317-4a1a-9d2e-9500c24a3239	29a2564e-49e3-4d14-86cb-d0450ff89d95	Demo MS 1500 checklist	MS 1500:2019	[{"category": "Cleaning", "criteria": "Equipment cleaned between batches", "severity": "critical"}, {"category": "Storage", "criteria": "Halal + non-halal segregation", "severity": "critical"}, {"category": "Documentation", "criteria": "SOP available on-site", "severity": "major"}]	2026-09-02 14:20:28.643868+07	2026-09-02 14:20:28.643868+07
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_logs (id, user_id, action, entity_type, entity_id, created_at, user_email, user_role, tenant_id, changes, metadata) FROM stdin;
b178a472-7839-4641-8330-d7c53f1b06bf	04c04132-3ce8-4314-930e-0eb6bec4a6a8	tenant_industry_assigned	tenant_industry_schema	a497cf80-bb63-425f-862e-7c95b4740032	2026-05-14 22:58:02.838052+07	\N	\N	\N	\N	{"schema_code": "food_manufacturing", "schema_name": "Cơ sở sản xuất thực phẩm"}
4057a52a-f87e-49e9-b526-17b743cf0643	ac9f756a-060f-4bf8-ab22-db96de5c790b	tenant_industry_assigned	tenant_industry_schema	a497cf80-bb63-425f-862e-7c95b4740032	2026-05-14 23:32:51.204254+07	\N	\N	\N	\N	{"schema_code": "food_manufacturing", "schema_name": "Cơ sở sản xuất thực phẩm"}
b9904f90-7b5c-4707-a75a-5c0f743dfd39	a9f5ce11-45af-4359-8c1f-ca6cb2cd01d6	tenant_industry_assigned	tenant_industry_schema	a497cf80-bb63-425f-862e-7c95b4740032	2026-05-14 23:40:54.082379+07	\N	\N	\N	\N	{"schema_code": "food_manufacturing", "schema_name": "Cơ sở sản xuất thực phẩm"}
b8db4ad9-4ffc-4e28-a8cd-9911ccab8599	90c2ba49-0cb8-4d9e-baab-f73064538f7a	tenant_industry_assigned	tenant_industry_schema	a497cf80-bb63-425f-862e-7c95b4740032	2026-05-14 23:46:05.674797+07	\N	\N	\N	\N	{"schema_code": "food_manufacturing", "schema_name": "Cơ sở sản xuất thực phẩm"}
4676884b-6cc5-4853-8ebd-3efc02c1e435	04c04132-3ce8-4314-930e-0eb6bec4a6a8	document.pdf_rendered	pdf_template	\N	2026-05-14 23:49:40.091159+07	demo-biz@aminra.vn	business	04c04132-3ce8-4314-930e-0eb6bec4a6a8	\N	{"ip": "172.19.0.7", "doc_type": "halal_policy", "is_draft": true, "byte_size": 114340, "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36", "duration_ms": 486, "filters_applied": ["validation", "source_merge", "placeholder_filler", "format", "truncation", "watermark"], "sources_versions": {"company": "df0b85d818345b80", "admin_cfg": "b2022adefbc7231a", "admin_assets": "021cdba9094c399c"}, "template_version": "v1", "filter_durations_ms": {"format": 0, "watermark": 0, "truncation": 0, "validation": 0, "source_merge": 0, "placeholder_filler": 0}, "placeholder_filled_fields": ["policy_id", "version", "mission_statement", "vision_statement", "scope_of_application", "commitment_clauses", "halal_committee", "references", "signatories"]}
d1729aa9-6959-4b2b-a7ab-9d843ab77081	04c04132-3ce8-4314-930e-0eb6bec4a6a8	document.pdf_rendered	pdf_template	\N	2026-05-14 23:53:05.385704+07	demo-biz@aminra.vn	business	04c04132-3ce8-4314-930e-0eb6bec4a6a8	\N	{"ip": "172.19.0.7", "doc_type": "company_profile", "is_draft": true, "byte_size": 89646, "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36", "duration_ms": 232, "filters_applied": ["validation", "source_merge", "placeholder_filler", "format", "truncation", "watermark"], "sources_versions": {"company": "df0b85d818345b80", "admin_cfg": "44136fa355b3678a", "admin_assets": "ded963762acbd84f"}, "template_version": "v1", "filter_durations_ms": {"format": 0, "watermark": 0, "truncation": 0, "validation": 4, "source_merge": 0, "placeholder_filler": 0}, "placeholder_filled_fields": ["tax_code", "factory_address", "website", "founded_year", "employee_count", "charter_capital", "halal_commitment", "business_activities", "products"]}
8deaae83-6237-47ea-a09f-628d4624d392	\N	anchor.submitted	blockchain_anchor	d3dd4a55-02f0-4091-9475-797e48a54af8	2026-05-16 16:11:20.822132+07	\N	\N	\N	\N	{"chain": "polygon", "tx_hash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "cert_count": 2, "batch_count": 0, "merkle_root": "0xb8cc71a897a5f6abc0ce684b90e326845c9f858126c4c53f17b2837ff5e361d7"}
ed8e4855-72fe-4a66-bab8-bf613a602f91	\N	anchor.submitted	blockchain_anchor	2bc82c86-2dcc-4266-942e-c9dfc4ab9f54	2026-05-16 16:11:20.969636+07	\N	\N	\N	\N	{"chain": "polygon", "tx_hash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "cert_count": 2, "batch_count": 0, "merkle_root": "0xb8cc71a897a5f6abc0ce684b90e326845c9f858126c4c53f17b2837ff5e361d7"}
34e05078-01e6-427a-8015-85190769dd21	\N	anchor.submitted	blockchain_anchor	3d708f9e-7fda-46e9-9519-0c8fc516dec0	2026-05-16 16:11:21.289401+07	\N	\N	\N	\N	{"chain": "polygon", "tx_hash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "cert_count": 2, "batch_count": 0, "merkle_root": "0xb8cc71a897a5f6abc0ce684b90e326845c9f858126c4c53f17b2837ff5e361d7"}
735af2c8-9644-4050-b179-3f2818ee78d5	4deb5b2e-349f-4510-96c4-d2a3d4c71ec7	tenant_industry_assigned	tenant_industry_schema	a497cf80-bb63-425f-862e-7c95b4740032	2026-09-10 01:20:33.266695+07	\N	\N	\N	\N	{"schema_code": "food_manufacturing", "schema_name": "Cơ sở sản xuất thực phẩm"}
\.


--
-- Data for Name: audit_ncr; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_ncr (id, visit_id, item_id, description, severity, photo_paths, corrective_action, deadline, status, evidence_paths, closed_at, closed_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: audit_visit_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_visit_items (id, visit_id, code, category, criteria, severity, result, clause, audit_method, documents, evidence, corrective_action, corrective_status, note, photo_paths, created_at) FROM stdin;
\.


--
-- Data for Name: audit_visits; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.audit_visits (id, business_tenant, provider_id, auditor_id, template_id, visit_type, status, scheduled_date, location, notes, auditor_signature_path, business_signature_path, start_gps, end_gps, report_pdf_path, compliance_score, created_at, updated_at) FROM stdin;
2ec274d3-b54f-449d-b72c-21ee6b1f07c8	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	29a2564e-49e3-4d14-86cb-d0450ff89d95	d560be17-c268-4ab0-b8d2-6d3f76eebcdc	81653e91-6317-4a1a-9d2e-9500c24a3239	initial	scheduled	2026-09-03	Bình Dương, VN	\N	\N	\N	\N	\N	\N	\N	2026-09-02 14:20:28.646729+07	2026-09-02 14:20:28.646729+07
\.


--
-- Data for Name: batch_anchor_proofs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.batch_anchor_proofs (batch_id, anchor_id, leaf_hash, leaf_index, proof_path, created_at) FROM stdin;
\.


--
-- Data for Name: batch_materials; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.batch_materials (batch_id, material_id, quantity, unit, supplier_id, eligibility_id, eligibility_snapshot) FROM stdin;
82437a08-6579-4bce-9eea-f86799e912e4	5b0061b9-c3f9-408d-978a-dfd5e361f70a	25.000	kg	\N	\N	{}
\.


--
-- Data for Name: batch_steps; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.batch_steps (id, batch_id, node_id, step_name, performed_by, started_at, completed_at, status, notes, photo_path, checklist, created_at, step_hash, approved_by, approved_at) FROM stdin;
8367ae6a-aac9-47ce-aebb-7ea44f32bf1e	89a80ffb-44b3-4165-90b7-ad76a57c4342	n_1789167215729	Bước mới	Nguyễn Văn A	\N	2026-09-12 05:54:53.744836+07	completed	\N	\N	[]	2026-09-12 05:54:08.432178+07	bacd879372a08bff6b0ebe42050f5eaaf8ea6926cb6138394b9bf41c88524ca6	abc@demo.com	2026-09-12 05:54:58.855336+07
4b758a5c-a5ba-4290-b287-687c6764745e	89a80ffb-44b3-4165-90b7-ad76a57c4342	n_1789167221361	Bước mới	Nguyễn Văn B	\N	2026-09-12 05:55:13.754462+07	completed	\N	\N	[]	2026-09-12 05:54:08.436968+07	00ce8e178cf56c7ca8b85fc9b217b875af2c8450c5690dc52afe4ab3b8fb62ed	abc@demo.com	2026-09-12 05:55:15.53941+07
0caa62a1-e488-433c-a05d-33ba81249a1c	89a80ffb-44b3-4165-90b7-ad76a57c4342	n_1789167223833	Bước mới	Nguyễn Văn C	\N	2026-09-12 05:55:17.61899+07	completed	\N	\N	[]	2026-09-12 05:54:08.438778+07	f3e81022a3bb702028cd87213e67985b6f933e55099da24d209e520b1a2d4eab	abc@demo.com	2026-09-12 05:55:18.82175+07
670b575e-8dba-49af-8b07-23436acee313	82437a08-6579-4bce-9eea-f86799e912e4	prep	Kiểm tra nguyên liệu	qa@demo.aminra.vn	2026-08-31 14:20:28.553469+07	2026-09-01 14:20:28.553469+07	completed	Demo step completed for smoke path	\N	[{"text": "COA hợp lệ", "checked": true}, {"text": "Halal cert còn hạn", "checked": true}]	2026-09-02 14:20:28.553469+07	\N	biz-demo-1@demo.aminra.vn	2026-09-01 14:20:28.553469+07
8cfad0fd-0237-44b1-b63e-63e2e8b3779d	82437a08-6579-4bce-9eea-f86799e912e4	mix	Trộn bột	qa@demo.aminra.vn	2026-08-31 14:20:28.575386+07	2026-09-01 14:20:28.575386+07	completed	Demo step completed for smoke path	\N	[{"text": "Dụng cụ đã vệ sinh", "checked": true}, {"text": "Không nhiễm chéo", "checked": true}]	2026-09-02 14:20:28.575386+07	\N	biz-demo-1@demo.aminra.vn	2026-09-01 14:20:28.575386+07
46d09733-6ee6-432e-9c39-6a492f84c00a	82437a08-6579-4bce-9eea-f86799e912e4	pack	Đóng gói	qa@demo.aminra.vn	2026-08-31 14:20:28.577386+07	2026-09-01 14:20:28.577386+07	completed	Demo step completed for smoke path	\N	[{"text": "Tem lô đúng", "checked": true}, {"text": "Khu đóng gói sạch", "checked": true}]	2026-09-02 14:20:28.577386+07	\N	biz-demo-1@demo.aminra.vn	2026-09-01 14:20:28.577386+07
\.


--
-- Data for Name: blockchain_anchors; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.blockchain_anchors (id, chain, merkle_root, tx_hash, block_number, cert_count, batch_count, submitted_at, confirmed_at, status, error_message, parent_anchor, metadata) FROM stdin;
\.


--
-- Data for Name: cert_anchor_proofs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.cert_anchor_proofs (cert_id, anchor_id, leaf_hash, leaf_index, proof_path, created_at) FROM stdin;
\.


--
-- Data for Name: certificate_risk_alerts; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.certificate_risk_alerts (id, impacted_tenant_id, supplier_id, certificate_id, event_type, severity, message, status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: custom_placeholders; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.custom_placeholders (id, key, label, description, default_value, source, is_system, created_at) FROM stdin;
\.


--
-- Data for Name: deletion_tokens; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.deletion_tokens (id, user_id, token, expires_at, confirmed_at, created_at) FROM stdin;
\.


--
-- Data for Name: documents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.documents (id, filename, original_filename, file_path, file_size, mime_type, user_id, tenant_id, doc_type, status, compliance_score, evaluation_result, uploaded_at, reviewed_by, reviewed_at, review_notes, cb_approved_at, version_number, version_parent_id, approver_id, approved_at, effective_date, next_review_date, retention_period_days, retention_expires_at, superseded_by_id, approval_status, dossier_id) FROM stdin;
06d7187b-702a-425f-868c-af1ee8df6dc3	demo-01-application_form.pdf	application_form.pdf	\N	102400	\N	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	application	uploaded	\N	\N	2026-09-02 14:20:28.579009+07	\N	\N	\N	\N	1	\N	\N	\N	\N	\N	1825	\N	\N	draft	\N
647a7047-4008-45fd-bc8f-80e57158410f	demo-02-ingredient_list.pdf	ingredient_list.pdf	\N	102400	\N	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	ingredient_list	uploaded	\N	\N	2026-09-02 14:20:28.586129+07	\N	\N	\N	\N	1	\N	\N	\N	\N	\N	1825	\N	\N	draft	\N
68b5d475-609c-4777-bc7c-192220c6cbbf	demo-03-sop_cleaning.pdf	sop_cleaning.pdf	\N	102400	\N	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	sop	uploaded	\N	\N	2026-09-02 14:20:28.590499+07	\N	\N	\N	\N	1	\N	\N	\N	\N	\N	1825	\N	\N	draft	\N
f63d3da5-1167-433f-adb5-f7a86ee67b40	demo-01-application_form.pdf	application_form.pdf	\N	102400	\N	69ac4987-8c50-46d2-8e1e-2482e738b7f6	69ac4987-8c50-46d2-8e1e-2482e738b7f6	application	uploaded	\N	\N	2026-09-02 14:20:28.59492+07	\N	\N	\N	\N	1	\N	\N	\N	\N	\N	1825	\N	\N	draft	\N
9bf1a53e-2a95-42b0-9fbd-3f1da3df9c6c	demo-02-ingredient_list.pdf	ingredient_list.pdf	\N	102400	\N	69ac4987-8c50-46d2-8e1e-2482e738b7f6	69ac4987-8c50-46d2-8e1e-2482e738b7f6	ingredient_list	uploaded	\N	\N	2026-09-02 14:20:28.597236+07	\N	\N	\N	\N	1	\N	\N	\N	\N	\N	1825	\N	\N	draft	\N
94bf3eaf-ee4e-4ab7-982c-f4f3039c87c7	demo-03-sop_cleaning.pdf	sop_cleaning.pdf	\N	102400	\N	69ac4987-8c50-46d2-8e1e-2482e738b7f6	69ac4987-8c50-46d2-8e1e-2482e738b7f6	sop	uploaded	\N	\N	2026-09-02 14:20:28.599578+07	\N	\N	\N	\N	1	\N	\N	\N	\N	\N	1825	\N	\N	draft	\N
\.


--
-- Data for Name: dossiers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dossiers (id, tenant_id, standard_type_id, title, status, notes, created_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: feature_flags; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.feature_flags (name, description, default_enabled, rollout_percentage, created_at, updated_at) FROM stdin;
ihc_meetings_v1	Internal Halal Committee meeting records (Tier-1 #22)	f	0	2026-05-03 09:05:34.396427+07	2026-05-03 09:05:34.396427+07
training_matrix_v1	Per-employee Halal training records (Tier-1 #23)	f	0	2026-05-03 09:05:34.396427+07	2026-05-03 09:05:34.396427+07
document_versioning_v1	Document approver/effective_date/retention (Tier-1 #24)	f	0	2026-05-03 09:05:34.396427+07	2026-05-03 09:05:34.396427+07
internal_audit_v1	Internal Halal audit module (Tier-1 #27, MS 1500 §5.10)	f	0	2026-05-03 09:05:34.396427+07	2026-05-03 09:05:34.396427+07
hazard_analysis_v1	Halal hazard analysis worksheet (Tier-1 #28)	f	0	2026-05-03 09:05:34.396427+07	2026-05-03 09:05:34.396427+07
ccp_table_v1	Halal Critical Control Points table (Tier-1 #29)	f	0	2026-05-03 09:05:34.396427+07	2026-05-03 09:05:34.396427+07
recall_workflow_v1	Complaint + recall workflow with mock-drill (Tier-1 #30)	f	0	2026-05-03 09:05:34.396427+07	2026-05-03 09:05:34.396427+07
pdf_html_renderer_v1.company_profile	Hồ sơ doanh nghiệp — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 06:12:29.074052+07
pdf_html_renderer_v1._style_guide	Internal — design system kitchen sink	t	100	2026-05-06 07:27:56.484154+07	2026-05-06 07:27:56.484154+07
pdf_html_renderer_v1.sop_raw_material_receiving	SOP nhận nguyên liệu — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 08:54:03.722754+07
pdf_html_renderer_v1.sop_storage_segregation	SOP lưu trữ và phân tách — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 08:54:03.722754+07
pdf_html_renderer_v1.sop_production_operation	SOP vận hành sản xuất — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 08:54:03.722754+07
pdf_html_renderer_v1.sop_cleaning_sanitation	SOP vệ sinh và làm sạch — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 08:54:03.722754+07
pdf_html_renderer_v1.sop_handling_nonconformances	SOP xử lý không phù hợp — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 08:54:03.722754+07
pdf_html_renderer_v1.sop_complaint_recall	SOP khiếu nại và thu hồi — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 08:54:03.722754+07
pdf_html_renderer_v1.halal_policy	Chính sách Halal — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 09:23:55.850588+07
pdf_html_renderer_v1.has_manual	Sổ tay HAS — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 09:23:55.850588+07
pdf_html_renderer_v1.halal_manual	Sổ tay Halal — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 09:23:55.850588+07
pdf_html_renderer_v1.generic	Generic fallback PDF template	t	100	2026-05-06 10:56:20.253495+07	2026-05-06 10:56:20.253495+07
pdf_html_renderer_v1.internal_halal_committee	Ban Halal nội bộ — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 10:56:20.253495+07
pdf_html_renderer_v1.ingredient_raw_material	Nguyên liệu thô — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 10:56:20.253495+07
pdf_html_renderer_v1.process_flow_chart	Sơ đồ quy trình — HTML render	t	0	2026-05-06 06:12:11.56042+07	2026-05-06 10:56:20.253495+07
\.


--
-- Data for Name: halal_certificates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.halal_certificates (id, submission_id, cert_number, issued_by, business_tenant, company_name, issue_date, expiry_date, pdf_path, status, notes, created_at, updated_at, revocation_reason, revoked_at, revoked_by, expiry_alerts_sent) FROM stdin;
05991b0a-be12-4284-849a-1a26349032d9	e6141eae-0533-4b3c-a9d1-9da191fd345d	HALAL-2026-DEMO	29a2564e-49e3-4d14-86cb-d0450ff89d95	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	Demo Foods Co.	2026-08-03	2027-08-03	\N	active	\N	2026-09-02 14:20:28.633715+07	2026-09-02 14:20:28.633715+07	\N	\N	\N	[]
f5c86145-c0bc-424a-9164-c1a67d2fc7ab	e1403f8d-6096-4c86-9f32-0868374aaac5	HALAL-2025-EXPIRING	29a2564e-49e3-4d14-86cb-d0450ff89d95	69ac4987-8c50-46d2-8e1e-2482e738b7f6	Demo Beverages Ltd.	2025-09-27	2026-09-27	\N	active	\N	2026-09-02 14:20:28.63731+07	2026-09-02 14:20:28.63731+07	\N	\N	\N	[]
\.


--
-- Data for Name: industry_schemas; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.industry_schemas (id, code, name_vi, name_en, description, jakim_scheme, icon, enabled, display_order, created_at, updated_at, created_by) FROM stdin;
a497cf80-bb63-425f-862e-7c95b4740032	food_manufacturing	Cơ sở sản xuất thực phẩm	Food Manufacturing	Halal coffee, bánh mì, đồ uống	MS 1500:2019	factory	t	1	2026-05-14 14:56:09.382223+07	2026-05-14 14:56:09.382223+07	\N
7bc5b329-77fc-466a-8cbc-ef0a4b0ff8a7	restaurant_hotel	Nhà hàng - Khách sạn Halal	Restaurant & Hotel	Dịch vụ ăn uống Halal	MS 1500	restaurant	t	2	2026-05-14 14:56:09.382223+07	2026-05-14 14:56:09.382223+07	\N
11ba4a3f-1c20-457f-87ee-d42d322ffee7	livestock_slaughter	Cơ sở chăn nuôi - Giết mổ	Livestock & Slaughter	Halal animal slaughter	MPPHM	cow	t	3	2026-05-14 14:56:09.382223+07	2026-05-14 14:56:09.382223+07	\N
\.


--
-- Data for Name: industry_standards; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.industry_standards (industry_schema_id, standard_type_id, is_default, display_order) FROM stdin;
\.


--
-- Data for Name: materials; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.materials (id, tenant_id, supplier_id, name, sku, category, halal_risk, description, unit, created_at, updated_at) FROM stdin;
5b0061b9-c3f9-408d-978a-dfd5e361f70a	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	08920f47-4bbe-4f62-a212-f76379b4b836	Bột mì Halal demo	FLOUR-HALAL-DEMO	ingredient	requires_cert	Nguyên liệu demo có chứng nhận Halal hợp lệ	kg	2026-09-02 14:20:28.534846+07	2026-09-02 14:20:28.534846+07
\.


--
-- Data for Name: member_invites; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.member_invites (id, tenant_id, email, invite_token, role, department, expires_at, accepted_at, created_at) FROM stdin;
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.notifications (id, user_id, type, title, message, read, link, created_at) FROM stdin;
\.


--
-- Data for Name: ops_user_link_backup_20260909; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.ops_user_link_backup_20260909 (backed_up_at, id, email, role, company_name, company_code, status, tenant_id, is_owner, invited_by, ihc_role, department, approved_by, approved_at, rejection_reason, created_at, updated_at, address, phone, representative_name, deleted_at, manager_name, permissions, notify_eval_done, notify_submission_reply, industry_schema_id, keycloak_sub) FROM stdin;
2026-09-10 01:44:23.768348+07	54182089-3a6d-458a-994d-93ac4e0c504f	admin@aminra.com	provider	AMINRA Platform	AMINRA-ADMIN	active	54182089-3a6d-458a-994d-93ac4e0c504f	t	\N	\N	\N	\N	\N	\N	2026-05-14 22:21:06.216712+07	2026-05-14 22:21:06.216712+07	\N	\N	\N	\N	\N	{}	t	t	\N	54182089-3a6d-458a-994d-93ac4e0c504f
\.


--
-- Data for Name: process_templates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.process_templates (id, tenant_id, name, description, flowchart, version, is_active, created_at, updated_at) FROM stdin;
85c3c44f-f54f-4bf5-b3fa-7882bef41ece	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	QA proxy process	\N	{"edges": [], "nodes": []}	1	t	2026-09-07 11:03:50.884937+07	2026-09-07 11:03:50.884937+07
5c5cf9e1-9672-437b-9627-b6cd4cb76ad9	67cb5be1-4c0a-4d7c-99e2-aa1432e051f1	Làm bánh mì		{"edges": [{"to": "n_1778212908197", "from": "n_1778212886829", "type": "sequential"}, {"to": "n_1778212955040", "from": "n_1778212908197", "type": "sequential"}, {"to": "n_1778212983984", "from": "n_1778212955040", "type": "sequential"}, {"to": "n_1778213050047", "from": "n_1778212983984", "type": "sequential"}, {"to": "n_1778213204296", "from": "n_1778213050047", "type": "sequential"}, {"to": "n_1778213218294", "from": "n_1778213204296", "type": "sequential"}], "nodes": [{"x": 250, "y": 120, "id": "n_1778212886829", "type": "main", "label": "Nhập nguyên liệu vào kho", "notes": "", "order": 1, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "", "conditions": "", "description": "", "responsible": ""}, {"x": 377, "y": 240, "id": "n_1778212908197", "type": "sub", "label": "Xuất phiếu nhập kho", "notes": "", "order": 2, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "", "conditions": "", "description": "", "responsible": ""}, {"x": 284, "y": 352, "id": "n_1778212955040", "type": "main", "label": "Nhào bột", "notes": "", "order": 3, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "Sử dụng nước chuẩn ", "conditions": "", "description": "", "responsible": ""}, {"x": 277, "y": 477, "id": "n_1778212983984", "type": "main", "label": "Trộn nguyên liệu", "notes": "", "order": 4, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "", "conditions": "37", "description": "", "responsible": "Nguyễn Văn C"}, {"x": 218, "y": 599, "id": "n_1778213050047", "type": "main", "label": "Nướng bánh", "notes": "", "order": 5, "children": [], "duration": "", "standard": "Nguyễn Văn D", "checklist": [], "equipment": "", "conditions": "220", "description": "", "responsible": ""}, {"x": 336, "y": 728, "id": "n_1778213204296", "type": "main", "label": "Để nguội", "notes": "", "order": 6, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "", "conditions": "", "description": "", "responsible": ""}, {"x": 226, "y": 855, "id": "n_1778213218294", "type": "main", "label": "Đóng bao", "notes": "", "order": 7, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "", "conditions": "", "description": "", "responsible": ""}]}	4	t	2026-05-08 11:00:54.874997+07	2026-05-08 11:07:35.82262+07
dfeb0a76-7bc2-4603-945a-8fbd4faa381b	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	Demo Halal Bakery Process	Quy trình demo cho lô bánh halal có trace QR	{"edges": [{"to": "mix", "from": "prep"}, {"to": "pack", "from": "mix"}], "nodes": [{"id": "prep", "label": "Kiểm tra nguyên liệu", "order": 1, "checklist": ["COA hợp lệ", "Halal cert còn hạn"]}, {"id": "mix", "label": "Trộn bột", "order": 2, "checklist": ["Dụng cụ đã vệ sinh", "Không nhiễm chéo"]}, {"id": "pack", "label": "Đóng gói", "order": 3, "checklist": ["Tem lô đúng", "Khu đóng gói sạch"]}]}	1	t	2026-09-02 14:20:28.540639+07	2026-09-02 14:20:28.540639+07
dde0e043-57c9-4121-8d6c-612923ced07b	4deb5b2e-349f-4510-96c4-d2a3d4c71ec7	sản xuất bánh mì		{"edges": [{"to": "n_1789167221361", "from": "n_1789167215729", "type": "sequential"}, {"to": "n_1789167223833", "from": "n_1789167221361", "type": "sequential"}], "nodes": [{"x": 212, "y": 23, "id": "n_1789167215729", "type": "main", "label": "Bước mới", "notes": "", "order": 1, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "", "conditions": "", "description": "", "responsible": ""}, {"x": 214, "y": 137, "id": "n_1789167221361", "type": "main", "label": "Bước mới", "notes": "", "order": 2, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "", "conditions": "", "description": "", "responsible": ""}, {"x": 216, "y": 262, "id": "n_1789167223833", "type": "main", "label": "Bước mới", "notes": "", "order": 3, "children": [], "duration": "", "standard": "", "checklist": [], "equipment": "", "conditions": "", "description": "", "responsible": ""}]}	2	t	2026-09-12 05:48:57.323391+07	2026-09-12 05:53:52.190714+07
83aa1dcc-06f7-41b0-951a-80095c27eadd	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	QA live process 1788753806	\N	{"edges": [], "nodes": []}	1	t	2026-09-07 11:03:26.099864+07	2026-09-07 11:03:26.099864+07
\.


--
-- Data for Name: production_batches; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.production_batches (id, tenant_id, batch_code, product_name, process_template_id, status, started_at, completed_at, compliance_score, qr_code_url, notes, created_at, updated_at, integrity_hash, sealed_data, assigned_to, assigned_name, approved_by, approved_at, public_trace_id, public_trace_enabled) FROM stdin;
82437a08-6579-4bce-9eea-f86799e912e4	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	LOT-2026-DEMO-TRACE	Demo Halal Sandwich Bread	dfeb0a76-7bc2-4603-945a-8fbd4faa381b	completed	2026-08-31 14:20:28.54431+07	2026-09-01 14:20:28.54431+07	100	http://localhost:3100/trace/LOT-2026-DEMO-TRACE	Demo trace batch with supplier/material/process linkage	2026-09-02 14:20:28.54431+07	2026-09-02 14:20:28.54431+07	\N	\N	\N	\N	\N	\N	a7cf654b-07bc-4838-afe3-f2acde2f5f4b	f
89a80ffb-44b3-4165-90b7-ad76a57c4342	4deb5b2e-349f-4510-96c4-d2a3d4c71ec7	LOT-001	Bánh mì Halal	dde0e043-57c9-4121-8d6c-612923ced07b	completed	2026-09-12 05:54:36.554857+07	2026-09-12 05:55:20.736302+07	100	https://dev-web.silvergem.org/trace/LOT-001		2026-09-12 05:54:08.410327+07	2026-09-12 05:55:30.952519+07	1eea1c1c3657e7c314449934cea749371741b8ea212d27b5fb575a0029cdb47d	{"steps": [{"notes": null, "status": "completed", "has_photo": false, "step_name": "Bước mới", "started_at": null, "approved_at": "2026-09-11T22:54:58.855336+00:00", "approved_by": "abc@demo.com", "completed_at": "2026-09-11T22:54:53.744836+00:00", "performed_by": "Nguyễn Văn A"}, {"notes": null, "status": "completed", "has_photo": false, "step_name": "Bước mới", "started_at": null, "approved_at": "2026-09-11T22:55:15.539410+00:00", "approved_by": "abc@demo.com", "completed_at": "2026-09-11T22:55:13.754462+00:00", "performed_by": "Nguyễn Văn B"}, {"notes": null, "status": "completed", "has_photo": false, "step_name": "Bước mới", "started_at": null, "approved_at": "2026-09-11T22:55:18.821750+00:00", "approved_by": "abc@demo.com", "completed_at": "2026-09-11T22:55:17.618990+00:00", "performed_by": "Nguyễn Văn C"}], "materials": [], "batch_code": "LOT-001", "started_at": "2026-09-11T22:54:36.554857+00:00", "approved_at": "2026-09-11T22:55:22.666799", "approved_by": "abc@demo.com", "completed_at": "2026-09-11T22:55:20.736302+00:00", "product_name": "Bánh mì Halal", "compliance_score": 100}	\N	\N	abc@demo.com	2026-09-12 05:55:22.672787+07	849e0dd2-d663-4fd5-9b76-82e1a3b386e3	f
\.


--
-- Data for Name: push_subscriptions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.push_subscriptions (id, user_id, endpoint, p256dh, auth, user_agent, created_at, last_used_at) FROM stdin;
\.


--
-- Data for Name: schema_doc_types; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.schema_doc_types (schema_id, doc_type, required, display_order) FROM stdin;
\.


--
-- Data for Name: standard_doc_types; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.standard_doc_types (standard_type_id, doc_type, required, display_order) FROM stdin;
\.


--
-- Data for Name: standard_types; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.standard_types (id, code, name_vi, name_en, organization, scheme_version, description, full_text_url, enabled, display_order, created_at, updated_at, created_by) FROM stdin;
\.


--
-- Data for Name: submission_comments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.submission_comments (id, submission_id, author_id, author_role, author_name, message, created_at) FROM stdin;
\.


--
-- Data for Name: submission_evaluations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.submission_evaluations (id, submission_id, auditor_id, checklist, score, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: submission_revision_requests; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.submission_revision_requests (id, submission_id, round, requester_id, requester_name, feedback, document_feedback, requested_at, resolved_at, business_response) FROM stdin;
778ca6e7-1f44-45b5-9663-bdea9539b3e1	a20da565-f04e-45c4-aecf-a2ce30a3161f	1	29a2564e-49e3-4d14-86cb-d0450ff89d95	Halal Certification Vietnam (Demo)	Cần bổ sung chứng nhận Halal của nguyên liệu hương liệu + sửa quy trình rửa thiết bị theo MS 1500 mục 5.4	[{"issue": "Thiếu seal JAKIM", "severity": "major", "suggestion": "Tải lại bản có seal", "document_id": "f63d3da5-1167-433f-adb5-f7a86ee67b40"}, {"issue": "Quy trình rửa thiết bị giữa ca", "severity": "critical", "suggestion": "Bổ sung istinjak step", "document_id": "94bf3eaf-ee4e-4ab7-982c-f4f3039c87c7"}]	2026-09-02 14:20:28.625499+07	\N	\N
\.


--
-- Data for Name: submissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.submissions (id, business_tenant, provider_id, auditor_id, document_ids, status, notes, auditor_notes, submitted_at, updated_at, company_name, deadline, revision_round, revision_requested_at, revision_resubmitted_at, sla_alerts_sent, archived_at) FROM stdin;
8e664be5-2026-40f2-ad67-af85a3b3a512	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	29a2564e-49e3-4d14-86cb-d0450ff89d95	\N	{06d7187b-702a-425f-868c-af1ee8df6dc3,647a7047-4008-45fd-bc8f-80e57158410f,68b5d475-609c-4777-bc7c-192220c6cbbf}	reviewing	Demo - Hồ sơ chứng nhận sản phẩm bánh mì gối	\N	2026-08-28 14:20:28.616576+07	2026-09-02 14:20:28.616576+07	Demo Foods Co.	2026-09-17 14:20:28.616576+07	0	\N	\N	[]	\N
a20da565-f04e-45c4-aecf-a2ce30a3161f	69ac4987-8c50-46d2-8e1e-2482e738b7f6	29a2564e-49e3-4d14-86cb-d0450ff89d95	\N	{f63d3da5-1167-433f-adb5-f7a86ee67b40,9bf1a53e-2a95-42b0-9fbd-3f1da3df9c6c,94bf3eaf-ee4e-4ab7-982c-f4f3039c87c7}	revision_required	Demo - Sản phẩm nước trái cây	\N	2026-08-23 14:20:28.621624+07	2026-09-02 14:20:28.621624+07	Demo Beverages Ltd.	2026-09-07 14:20:28.621624+07	1	2026-08-31 14:20:28.621624+07	\N	[]	\N
e6141eae-0533-4b3c-a9d1-9da191fd345d	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	29a2564e-49e3-4d14-86cb-d0450ff89d95	\N	{06d7187b-702a-425f-868c-af1ee8df6dc3,647a7047-4008-45fd-bc8f-80e57158410f,68b5d475-609c-4777-bc7c-192220c6cbbf}	approved	Demo - Đã được duyệt, chuẩn bị cấp cert	\N	2026-08-13 14:20:28.629787+07	2026-08-31 14:20:28.629787+07	Demo Foods Co.	\N	0	\N	\N	[]	\N
e1403f8d-6096-4c86-9f32-0868374aaac5	69ac4987-8c50-46d2-8e1e-2482e738b7f6	29a2564e-49e3-4d14-86cb-d0450ff89d95	\N	{f63d3da5-1167-433f-adb5-f7a86ee67b40,9bf1a53e-2a95-42b0-9fbd-3f1da3df9c6c,94bf3eaf-ee4e-4ab7-982c-f4f3039c87c7}	approved	Demo - Hồ sơ cấp năm ngoái, cert sắp hết hạn	\N	2025-09-27 14:20:28.631646+07	2025-10-02 14:20:28.631646+07	Demo Beverages Ltd.	\N	0	\N	\N	[]	\N
\.


--
-- Data for Name: supplier_certificates; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.supplier_certificates (id, supplier_id, tenant_id, cert_type, cert_number, issuing_body, issued_date, expiry_date, file_path, original_filename, file_size, created_at, uploaded_by) FROM stdin;
fcb923ca-0f04-4aeb-aea6-bc22b91244da	08920f47-4bbe-4f62-a212-f76379b4b836	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	Halal	JAKIM-DEMO-2026	JAKIM	2026-07-19	2027-07-19	\N	jakim-demo-certificate.pdf	102400	2026-09-02 14:20:28.530034+07	\N
\.


--
-- Data for Name: supplier_eligibilities; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.supplier_eligibilities (id, supplier_id, tenant_id, certificate_no, issuer_name, status, valid_from, valid_until, scope, source_of_truth, changed_at, changed_by, reason, created_at, updated_at, provider_id, source_certificate_id) FROM stdin;
\.


--
-- Data for Name: suppliers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.suppliers (id, tenant_id, name, address, phone, email, contact_person, supplier_type, status, notes, created_at, updated_at, tax_code, invite_token, invite_expires_at) FROM stdin;
08920f47-4bbe-4f62-a212-f76379b4b836	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	Demo Halal Ingredients Supplier	KCN VSIP, Bình Dương	0901234567	qa@demo-supplier.vn	Nguyễn Halal	ingredient	verified	Demo supplier with valid JAKIM certificate	2026-09-02 14:20:28.525224+07	2026-09-02 14:20:28.525224+07	0312345678	\N	\N
\.


--
-- Data for Name: supply_relationships; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.supply_relationships (id, buyer_tenant_id, supplier_tenant_id, supplier_id, material_category, status, last_purchase_at, created_at) FROM stdin;
\.


--
-- Data for Name: tenant_feature_overrides; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tenant_feature_overrides (tenant_id, feature_name, enabled, override_reason, created_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, email, role, company_name, company_code, status, tenant_id, is_owner, invited_by, ihc_role, department, approved_by, approved_at, rejection_reason, created_at, updated_at, address, phone, representative_name, deleted_at, manager_name, permissions, notify_eval_done, notify_submission_reply, industry_schema_id, keycloak_sub) FROM stdin;
6eb82c5e-d678-49e5-b242-7880bb7bd0a7	biz-demo-1@demo.aminra.vn	business	Demo Foods Co.	BIZ-DEMO-001	active	6eb82c5e-d678-49e5-b242-7880bb7bd0a7	t	\N	\N	\N	\N	\N	\N	2026-09-02 14:20:25.597477+07	2026-09-02 14:20:25.597477+07	QA Address 1788926559	0900000000	QA Rep 1788926559	\N	QA Manager 1788926559	{}	t	t	\N	70772b1a-c8db-4f13-9e0e-69c87571f7eb
c0ab3bff-043d-4c84-aaed-c0cdc411a182	khaleddinh@protonmail.com	business	khaleddinh	\N	pending	\N	f	\N	\N	\N	\N	\N	\N	2026-09-07 20:02:37.300903+07	2026-09-07 20:02:37.300903+07	\N	\N	\N	\N	\N	{}	t	t	\N	79e4dcea-80e1-4d51-8b7f-5ebc91762750
fe074982-2b2d-4070-8a60-022fa98e9d59	provowner-1778752769@aminra.vn	provider	CB Co	\N	active	fe074982-2b2d-4070-8a60-022fa98e9d59	t	\N	\N	\N	\N	\N	\N	2026-05-14 16:59:32.350378+07	2026-05-14 16:59:32.350378+07	\N	\N	\N	\N	\N	{}	t	t	\N	e7c75905-e8f4-4564-8e8c-036e41748429
828b8455-bad2-4ccf-9f27-7ce1831ff25a	auditor-1778752772@aminra.vn	provider	Test Auditor	\N	active	fe074982-2b2d-4070-8a60-022fa98e9d59	f	fe074982-2b2d-4070-8a60-022fa98e9d59	\N	halal_food	\N	\N	\N	2026-05-14 16:59:34.730205+07	2026-05-14 16:59:34.730205+07	\N	\N	\N	\N	\N	{}	t	t	\N	00b31821-7c7f-4559-9ae2-e3a4714698eb
2af450b0-49c0-4524-8512-f37a225997b8	invitee-1778752881@aminra.vn	business	Invitee Final	\N	active	5e14f49d-a739-4f27-a455-de3c090e1526	f	\N	qa	QA	\N	\N	\N	2026-05-14 17:01:24.021701+07	2026-05-14 17:01:24.021701+07	\N	\N	\N	\N	\N	{}	t	t	\N	d527e8cf-fc7b-4fe7-aeab-632778c35038
4deb5b2e-349f-4510-96c4-d2a3d4c71ec7	abc@demo.com	business	Công ty ABC	\N	active	4deb5b2e-349f-4510-96c4-d2a3d4c71ec7	t	\N	\N	\N	\N	\N	\N	2026-09-08 07:41:24.174929+07	2026-09-08 07:41:24.174929+07	\N	\N	\N	\N	\N	{}	t	t	a497cf80-bb63-425f-862e-7c95b4740032	4deb5b2e-349f-4510-96c4-d2a3d4c71ec7
7ae79379-10a8-4f70-9c57-8cbed16fee26	pw-tier1-biz-1788824394822@e2e.vn	business	pw-tier1-biz-1788824394822	\N	pending	\N	f	\N	\N	\N	\N	\N	\N	2026-09-08 06:39:56.549562+07	2026-09-08 06:39:56.549562+07	\N	\N	\N	\N	\N	{}	t	t	\N	fdec9faf-51b2-4a25-9a31-a94877f9abbb
e1e482e9-7168-4d5f-ab30-1ab3d00db811	pw-tier1-biz-1788824682538@e2e.vn	business	pw-tier1-biz-1788824682538	\N	pending	\N	f	\N	\N	\N	\N	\N	\N	2026-09-08 06:45:14.423522+07	2026-09-08 06:45:14.423522+07	\N	\N	\N	\N	\N	{}	t	t	\N	7f552587-0130-4c3e-b219-f603492755d6
c1d8c1d1-a85d-40e2-93c6-aa579da1e57e	uat-92d5b194-a02-677a@aminra-qa.com	business	UAT-92d5b194	UAT-92d5b194	active	c1d8c1d1-a85d-40e2-93c6-aa579da1e57e	t	\N	\N	\N	\N	\N	\N	2026-05-14 17:23:22.597963+07	2026-05-14 17:23:22.597963+07	\N	\N	\N	\N	\N	{}	t	t	\N	2e2bd927-7b54-429f-bfed-a1655b51cb91
54182089-3a6d-458a-994d-93ac4e0c504f	admin@aminra.com	provider	AMINRA Platform	AMINRA-ADMIN	active	54182089-3a6d-458a-994d-93ac4e0c504f	t	\N	\N	\N	\N	\N	\N	2026-05-14 22:21:06.216712+07	2026-05-14 22:21:06.216712+07	\N	\N	\N	\N	\N	{}	t	t	\N	54182089-3a6d-458a-994d-93ac4e0c504f
90c2ba49-0cb8-4d9e-baab-f73064538f7a	kc-sub-smoke-721749fd@aminra-qa.com	business	Smoke Co — verified 6c89c015	\N	active	90c2ba49-0cb8-4d9e-baab-f73064538f7a	t	\N	\N	\N	\N	\N	\N	2026-05-14 23:46:04.93543+07	2026-05-14 23:46:04.93543+07	GET-roundtrip St	\N	\N	\N	\N	{}	t	t	a497cf80-bb63-425f-862e-7c95b4740032	90c2ba49-0cb8-4d9e-baab-f73064538f7a
ac9f756a-060f-4bf8-ab22-db96de5c790b	kc-sub-smoke-2f7b1b6f@aminra-qa.com	business	KCSubSmoke (renamed)	\N	active	ac9f756a-060f-4bf8-ab22-db96de5c790b	t	\N	\N	\N	\N	\N	\N	2026-05-14 23:32:50.345702+07	2026-05-14 23:32:50.345702+07	\N	\N	\N	\N	\N	{}	t	t	a497cf80-bb63-425f-862e-7c95b4740032	ac9f756a-060f-4bf8-ab22-db96de5c790b
a9f5ce11-45af-4359-8c1f-ca6cb2cd01d6	kc-sub-smoke-ac9661a0@aminra-qa.com	business	Smoke Co — verified 482d98e2	\N	active	a9f5ce11-45af-4359-8c1f-ca6cb2cd01d6	t	\N	\N	\N	\N	\N	\N	2026-05-14 23:40:53.693296+07	2026-05-14 23:40:53.693296+07	GET-roundtrip St	\N	\N	\N	\N	{}	t	t	a497cf80-bb63-425f-862e-7c95b4740032	a9f5ce11-45af-4359-8c1f-ca6cb2cd01d6
04c04132-3ce8-4314-930e-0eb6bec4a6a8	demo-biz@aminra.vn	business	DEMO BIZ FINAL TEST 1778776818	\N	active	04c04132-3ce8-4314-930e-0eb6bec4a6a8	t	\N	\N	\N	\N	\N	\N	2026-05-14 22:48:03.865749+07	2026-05-14 22:48:03.865749+07	Final Test St 999	+84999888777	Nguyen Van X	\N	Manager Y	{}	t	t	a497cf80-bb63-425f-862e-7c95b4740032	04c04132-3ce8-4314-930e-0eb6bec4a6a8
0524b0e5-2c85-4e2c-8ed1-1ca7058a5632	demo-platform-admin@demo.aminra.vn	provider	AMINRA Platform Admin (Demo)	ADMIN-DEMO-001	active	0524b0e5-2c85-4e2c-8ed1-1ca7058a5632	t	\N	\N	\N	\N	\N	\N	2026-09-02 14:20:22.185223+07	2026-09-02 14:20:22.185223+07	\N	\N	\N	\N	\N	{}	t	t	\N	4deab68a-5f55-4c3a-8a33-e2c5e778a50f
29a2564e-49e3-4d14-86cb-d0450ff89d95	cb-demo@demo.aminra.vn	provider	Halal Certification Vietnam (Demo)	CB-DEMO-001	active	29a2564e-49e3-4d14-86cb-d0450ff89d95	t	\N	\N	\N	\N	\N	\N	2026-09-02 14:20:23.915437+07	2026-09-02 14:20:23.915437+07	\N	\N	\N	\N	\N	{}	t	t	\N	38acfe95-d9d7-454f-8bcc-577e872cc812
69ac4987-8c50-46d2-8e1e-2482e738b7f6	biz-demo-2@demo.aminra.vn	business	Demo Beverages Ltd.	BIZ-DEMO-002	active	69ac4987-8c50-46d2-8e1e-2482e738b7f6	t	\N	\N	\N	\N	\N	\N	2026-09-02 14:20:27.087906+07	2026-09-02 14:20:27.087906+07	\N	\N	\N	\N	\N	{}	t	t	\N	30c70cf8-b7de-408b-8fbc-9e189367ab83
d560be17-c268-4ab0-b8d2-6d3f76eebcdc	auditor-demo@demo.aminra.vn	provider	Halal Certification Vietnam (Demo)	AUDITOR-DEMO-001	active	29a2564e-49e3-4d14-86cb-d0450ff89d95	f	\N	\N	\N	\N	\N	\N	2026-09-02 14:20:28.521336+07	2026-09-02 14:20:28.521336+07	\N	\N	\N	\N	\N	{}	t	t	\N	f9e21f5d-4205-45a6-b02c-a55d74dcab4a
68ecaf9b-201a-402f-a673-f5a4c2626a20	beensand97@gmail.com	business	beensand97	\N	pending	\N	f	\N	\N	\N	\N	\N	\N	2026-09-02 12:41:34.63175+07	2026-09-02 12:41:34.63175+07	\N	\N	\N	\N	\N	{}	t	t	\N	68ecaf9b-201a-402f-a673-f5a4c2626a20
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_checklist_templates audit_checklist_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_checklist_templates
    ADD CONSTRAINT audit_checklist_templates_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: audit_ncr audit_ncr_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_ncr
    ADD CONSTRAINT audit_ncr_pkey PRIMARY KEY (id);


--
-- Name: audit_visit_items audit_visit_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_visit_items
    ADD CONSTRAINT audit_visit_items_pkey PRIMARY KEY (id);


--
-- Name: audit_visits audit_visits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_visits
    ADD CONSTRAINT audit_visits_pkey PRIMARY KEY (id);


--
-- Name: batch_anchor_proofs batch_anchor_proofs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_anchor_proofs
    ADD CONSTRAINT batch_anchor_proofs_pkey PRIMARY KEY (batch_id, anchor_id);


--
-- Name: batch_materials batch_materials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_materials
    ADD CONSTRAINT batch_materials_pkey PRIMARY KEY (batch_id, material_id);


--
-- Name: batch_steps batch_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_steps
    ADD CONSTRAINT batch_steps_pkey PRIMARY KEY (id);


--
-- Name: blockchain_anchors blockchain_anchors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.blockchain_anchors
    ADD CONSTRAINT blockchain_anchors_pkey PRIMARY KEY (id);


--
-- Name: cert_anchor_proofs cert_anchor_proofs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cert_anchor_proofs
    ADD CONSTRAINT cert_anchor_proofs_pkey PRIMARY KEY (cert_id, anchor_id);


--
-- Name: certificate_risk_alerts certificate_risk_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_risk_alerts
    ADD CONSTRAINT certificate_risk_alerts_pkey PRIMARY KEY (id);


--
-- Name: custom_placeholders custom_placeholders_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_placeholders
    ADD CONSTRAINT custom_placeholders_key_key UNIQUE (key);


--
-- Name: custom_placeholders custom_placeholders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_placeholders
    ADD CONSTRAINT custom_placeholders_pkey PRIMARY KEY (id);


--
-- Name: deletion_tokens deletion_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deletion_tokens
    ADD CONSTRAINT deletion_tokens_pkey PRIMARY KEY (id);


--
-- Name: deletion_tokens deletion_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deletion_tokens
    ADD CONSTRAINT deletion_tokens_token_key UNIQUE (token);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: dossiers dossiers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dossiers
    ADD CONSTRAINT dossiers_pkey PRIMARY KEY (id);


--
-- Name: feature_flags feature_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feature_flags
    ADD CONSTRAINT feature_flags_pkey PRIMARY KEY (name);


--
-- Name: halal_certificates halal_certificates_cert_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.halal_certificates
    ADD CONSTRAINT halal_certificates_cert_number_key UNIQUE (cert_number);


--
-- Name: halal_certificates halal_certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.halal_certificates
    ADD CONSTRAINT halal_certificates_pkey PRIMARY KEY (id);


--
-- Name: industry_schemas industry_schemas_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.industry_schemas
    ADD CONSTRAINT industry_schemas_code_key UNIQUE (code);


--
-- Name: industry_schemas industry_schemas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.industry_schemas
    ADD CONSTRAINT industry_schemas_pkey PRIMARY KEY (id);


--
-- Name: industry_standards industry_standards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.industry_standards
    ADD CONSTRAINT industry_standards_pkey PRIMARY KEY (industry_schema_id, standard_type_id);


--
-- Name: materials materials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_pkey PRIMARY KEY (id);


--
-- Name: member_invites member_invites_invite_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_invites
    ADD CONSTRAINT member_invites_invite_token_key UNIQUE (invite_token);


--
-- Name: member_invites member_invites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_invites
    ADD CONSTRAINT member_invites_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: process_templates process_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.process_templates
    ADD CONSTRAINT process_templates_pkey PRIMARY KEY (id);


--
-- Name: production_batches production_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_pkey PRIMARY KEY (id);


--
-- Name: push_subscriptions push_subscriptions_endpoint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_endpoint_key UNIQUE (endpoint);


--
-- Name: push_subscriptions push_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: schema_doc_types schema_doc_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_doc_types
    ADD CONSTRAINT schema_doc_types_pkey PRIMARY KEY (schema_id, doc_type);


--
-- Name: standard_doc_types standard_doc_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.standard_doc_types
    ADD CONSTRAINT standard_doc_types_pkey PRIMARY KEY (standard_type_id, doc_type);


--
-- Name: standard_types standard_types_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.standard_types
    ADD CONSTRAINT standard_types_code_key UNIQUE (code);


--
-- Name: standard_types standard_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.standard_types
    ADD CONSTRAINT standard_types_pkey PRIMARY KEY (id);


--
-- Name: submission_comments submission_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_comments
    ADD CONSTRAINT submission_comments_pkey PRIMARY KEY (id);


--
-- Name: submission_evaluations submission_evaluations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_evaluations
    ADD CONSTRAINT submission_evaluations_pkey PRIMARY KEY (id);


--
-- Name: submission_evaluations submission_evaluations_submission_id_auditor_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_evaluations
    ADD CONSTRAINT submission_evaluations_submission_id_auditor_id_key UNIQUE (submission_id, auditor_id);


--
-- Name: submission_revision_requests submission_revision_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_revision_requests
    ADD CONSTRAINT submission_revision_requests_pkey PRIMARY KEY (id);


--
-- Name: submission_revision_requests submission_revision_requests_submission_id_round_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_revision_requests
    ADD CONSTRAINT submission_revision_requests_submission_id_round_key UNIQUE (submission_id, round);


--
-- Name: submissions submissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_pkey PRIMARY KEY (id);


--
-- Name: supplier_certificates supplier_certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_certificates
    ADD CONSTRAINT supplier_certificates_pkey PRIMARY KEY (id);


--
-- Name: supplier_eligibilities supplier_eligibilities_one_per_supplier; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_eligibilities
    ADD CONSTRAINT supplier_eligibilities_one_per_supplier UNIQUE (supplier_id);


--
-- Name: supplier_eligibilities supplier_eligibilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_eligibilities
    ADD CONSTRAINT supplier_eligibilities_pkey PRIMARY KEY (id);


--
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (id);


--
-- Name: supply_relationships supply_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supply_relationships
    ADD CONSTRAINT supply_relationships_pkey PRIMARY KEY (id);


--
-- Name: tenant_feature_overrides tenant_feature_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_feature_overrides
    ADD CONSTRAINT tenant_feature_overrides_pkey PRIMARY KEY (tenant_id, feature_name);


--
-- Name: production_batches uq_production_batches_tenant_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT uq_production_batches_tenant_code UNIQUE (tenant_id, batch_code);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_keycloak_sub_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_keycloak_sub_key UNIQUE (keycloak_sub);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_anchor_chain_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_anchor_chain_status ON public.blockchain_anchors USING btree (chain, status);


--
-- Name: idx_anchor_submitted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_anchor_submitted ON public.blockchain_anchors USING btree (submitted_at DESC);


--
-- Name: idx_anchor_tx_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_anchor_tx_hash ON public.blockchain_anchors USING btree (tx_hash) WHERE (tx_hash IS NOT NULL);


--
-- Name: idx_audit_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_action ON public.audit_logs USING btree (action, created_at DESC);


--
-- Name: idx_audit_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_created ON public.audit_logs USING btree (created_at DESC);


--
-- Name: idx_audit_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_entity ON public.audit_logs USING btree (entity_type, entity_id, created_at DESC);


--
-- Name: idx_audit_logs_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_created ON public.audit_logs USING btree (created_at);


--
-- Name: idx_audit_logs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_user_id ON public.audit_logs USING btree (user_id);


--
-- Name: idx_audit_ncr_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_ncr_status ON public.audit_ncr USING btree (status);


--
-- Name: idx_audit_ncr_visit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_ncr_visit ON public.audit_ncr USING btree (visit_id);


--
-- Name: idx_audit_templates_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_templates_provider ON public.audit_checklist_templates USING btree (provider_id);


--
-- Name: idx_audit_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_tenant ON public.audit_logs USING btree (tenant_id, created_at DESC);


--
-- Name: idx_audit_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_user ON public.audit_logs USING btree (user_id, created_at DESC);


--
-- Name: idx_audit_visit_items_visit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_visit_items_visit ON public.audit_visit_items USING btree (visit_id);


--
-- Name: idx_audit_visits_auditor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_visits_auditor ON public.audit_visits USING btree (auditor_id);


--
-- Name: idx_audit_visits_business; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_visits_business ON public.audit_visits USING btree (business_tenant);


--
-- Name: idx_audit_visits_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_visits_provider ON public.audit_visits USING btree (provider_id);


--
-- Name: idx_audit_visits_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_visits_status ON public.audit_visits USING btree (status);


--
-- Name: idx_batch_materials_supplier_eligibility; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_batch_materials_supplier_eligibility ON public.batch_materials USING btree (supplier_id, eligibility_id);


--
-- Name: idx_batch_proof_anchor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_batch_proof_anchor ON public.batch_anchor_proofs USING btree (anchor_id);


--
-- Name: idx_batch_proof_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_batch_proof_batch ON public.batch_anchor_proofs USING btree (batch_id);


--
-- Name: idx_batch_steps_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_batch_steps_batch ON public.batch_steps USING btree (batch_id);


--
-- Name: idx_cert_proof_anchor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cert_proof_anchor ON public.cert_anchor_proofs USING btree (anchor_id);


--
-- Name: idx_cert_proof_cert; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cert_proof_cert ON public.cert_anchor_proofs USING btree (cert_id);


--
-- Name: idx_certificate_risk_alerts_impacted_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_certificate_risk_alerts_impacted_status ON public.certificate_risk_alerts USING btree (impacted_tenant_id, status, created_at DESC);


--
-- Name: idx_certificate_risk_alerts_supplier_cert; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_certificate_risk_alerts_supplier_cert ON public.certificate_risk_alerts USING btree (supplier_id, certificate_id);


--
-- Name: idx_certificates_business; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_certificates_business ON public.halal_certificates USING btree (business_tenant);


--
-- Name: idx_certificates_submission; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_certificates_submission ON public.halal_certificates USING btree (submission_id);


--
-- Name: idx_certs_expiry_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_certs_expiry_active ON public.halal_certificates USING btree (expiry_date) WHERE ((status)::text = 'active'::text);


--
-- Name: idx_comments_submission; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_comments_submission ON public.submission_comments USING btree (submission_id);


--
-- Name: idx_custom_placeholders_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_custom_placeholders_key ON public.custom_placeholders USING btree (key);


--
-- Name: idx_deletion_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deletion_token ON public.deletion_tokens USING btree (token);


--
-- Name: idx_deletion_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deletion_user ON public.deletion_tokens USING btree (user_id, created_at DESC);


--
-- Name: idx_documents_dossier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_dossier ON public.documents USING btree (dossier_id) WHERE (dossier_id IS NOT NULL);


--
-- Name: idx_documents_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_status ON public.documents USING btree (status);


--
-- Name: idx_documents_superseded_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_superseded_by ON public.documents USING btree (superseded_by_id) WHERE (superseded_by_id IS NOT NULL);


--
-- Name: idx_documents_tenant_approval; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_tenant_approval ON public.documents USING btree (tenant_id, approval_status);


--
-- Name: idx_documents_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_tenant_id ON public.documents USING btree (tenant_id);


--
-- Name: idx_documents_tenant_next_review; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_tenant_next_review ON public.documents USING btree (tenant_id, next_review_date) WHERE (next_review_date IS NOT NULL);


--
-- Name: idx_documents_tenant_retention; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_tenant_retention ON public.documents USING btree (tenant_id, retention_expires_at) WHERE (retention_expires_at IS NOT NULL);


--
-- Name: idx_documents_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_user_id ON public.documents USING btree (user_id);


--
-- Name: idx_documents_version_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_version_parent ON public.documents USING btree (version_parent_id) WHERE (version_parent_id IS NOT NULL);


--
-- Name: idx_dossiers_standard; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dossiers_standard ON public.dossiers USING btree (standard_type_id);


--
-- Name: idx_dossiers_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dossiers_tenant ON public.dossiers USING btree (tenant_id, status, created_at DESC);


--
-- Name: idx_evaluations_submission; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_evaluations_submission ON public.submission_evaluations USING btree (submission_id);


--
-- Name: idx_industry_schemas_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_industry_schemas_enabled ON public.industry_schemas USING btree (enabled, display_order);


--
-- Name: idx_industry_standards_industry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_industry_standards_industry ON public.industry_standards USING btree (industry_schema_id, display_order);


--
-- Name: idx_materials_supplier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_materials_supplier ON public.materials USING btree (supplier_id);


--
-- Name: idx_materials_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_materials_tenant ON public.materials USING btree (tenant_id);


--
-- Name: idx_member_invites_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_member_invites_tenant ON public.member_invites USING btree (tenant_id);


--
-- Name: idx_member_invites_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_member_invites_token ON public.member_invites USING btree (invite_token);


--
-- Name: idx_notifications_user_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_user_read ON public.notifications USING btree (user_id, read);


--
-- Name: idx_production_batches_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_production_batches_status ON public.production_batches USING btree (status);


--
-- Name: idx_production_batches_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_production_batches_tenant ON public.production_batches USING btree (tenant_id);


--
-- Name: idx_push_subscriptions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_push_subscriptions_user_id ON public.push_subscriptions USING btree (user_id);


--
-- Name: idx_revision_requests_submission; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revision_requests_submission ON public.submission_revision_requests USING btree (submission_id, round DESC);


--
-- Name: idx_revision_requests_unresolved; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revision_requests_unresolved ON public.submission_revision_requests USING btree (submission_id) WHERE (resolved_at IS NULL);


--
-- Name: idx_schema_doc_types_schema; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_schema_doc_types_schema ON public.schema_doc_types USING btree (schema_id, display_order);


--
-- Name: idx_standard_doc_types_std; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_standard_doc_types_std ON public.standard_doc_types USING btree (standard_type_id, display_order);


--
-- Name: idx_standard_types_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_standard_types_enabled ON public.standard_types USING btree (enabled, display_order);


--
-- Name: idx_submissions_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_active ON public.submissions USING btree (provider_id, business_tenant) WHERE (archived_at IS NULL);


--
-- Name: idx_submissions_auditor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_auditor ON public.submissions USING btree (auditor_id);


--
-- Name: idx_submissions_business; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_business ON public.submissions USING btree (business_tenant);


--
-- Name: idx_submissions_deadline; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_deadline ON public.submissions USING btree (deadline);


--
-- Name: idx_submissions_deadline_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_deadline_active ON public.submissions USING btree (deadline) WHERE ((deadline IS NOT NULL) AND ((status)::text <> ALL ((ARRAY['approved'::character varying, 'returned'::character varying, 'rejected'::character varying])::text[])));


--
-- Name: idx_submissions_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_provider ON public.submissions USING btree (provider_id);


--
-- Name: idx_submissions_revision_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_revision_state ON public.submissions USING btree (status, revision_round) WHERE ((status)::text = 'revision_required'::text);


--
-- Name: idx_submissions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_submissions_status ON public.submissions USING btree (status);


--
-- Name: idx_supplier_certs_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supplier_certs_expiry ON public.supplier_certificates USING btree (expiry_date);


--
-- Name: idx_supplier_certs_supplier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supplier_certs_supplier ON public.supplier_certificates USING btree (supplier_id);


--
-- Name: idx_supplier_eligibilities_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supplier_eligibilities_provider ON public.supplier_eligibilities USING btree (provider_id, tenant_id, status);


--
-- Name: idx_supplier_eligibilities_source_cert; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supplier_eligibilities_source_cert ON public.supplier_eligibilities USING btree (source_certificate_id);


--
-- Name: idx_supplier_eligibilities_status_valid_until; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supplier_eligibilities_status_valid_until ON public.supplier_eligibilities USING btree (status, valid_until);


--
-- Name: idx_supplier_eligibilities_tenant_supplier_status_dates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supplier_eligibilities_tenant_supplier_status_dates ON public.supplier_eligibilities USING btree (tenant_id, supplier_id, status, valid_from, valid_until);


--
-- Name: idx_suppliers_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_suppliers_tenant ON public.suppliers USING btree (tenant_id);


--
-- Name: idx_supply_relationships_buyer_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supply_relationships_buyer_active ON public.supply_relationships USING btree (buyer_tenant_id, status, supplier_id);


--
-- Name: idx_supply_relationships_supplier_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supply_relationships_supplier_active ON public.supply_relationships USING btree (supplier_id, status, buyer_tenant_id);


--
-- Name: idx_tenant_feature_overrides_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenant_feature_overrides_tenant ON public.tenant_feature_overrides USING btree (tenant_id);


--
-- Name: idx_users_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_deleted_at ON public.users USING btree (deleted_at) WHERE (deleted_at IS NOT NULL);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_industry_schema; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_industry_schema ON public.users USING btree (industry_schema_id);


--
-- Name: idx_users_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_role ON public.users USING btree (role);


--
-- Name: idx_users_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_status ON public.users USING btree (status);


--
-- Name: idx_users_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_tenant_id ON public.users USING btree (tenant_id);


--
-- Name: ix_users_keycloak_sub; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_keycloak_sub ON public.users USING btree (keycloak_sub);


--
-- Name: uq_production_batches_public_trace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_production_batches_public_trace_id ON public.production_batches USING btree (public_trace_id);


--
-- Name: uq_suppliers_invite_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_suppliers_invite_token ON public.suppliers USING btree (invite_token) WHERE (invite_token IS NOT NULL);


--
-- Name: documents documents_block_delete_with_children; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER documents_block_delete_with_children BEFORE DELETE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.block_delete_with_children();


--
-- Name: documents documents_chain_tenant_check; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER documents_chain_tenant_check BEFORE INSERT OR UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.enforce_documents_chain_tenant();


--
-- Name: audit_logs trg_audit_logs_immutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_logs_immutable BEFORE DELETE OR UPDATE ON public.audit_logs FOR EACH ROW EXECUTE FUNCTION public.audit_logs_immutable_guard();


--
-- Name: audit_checklist_templates update_audit_checklist_templates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_audit_checklist_templates_updated_at BEFORE UPDATE ON public.audit_checklist_templates FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: audit_ncr update_audit_ncr_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_audit_ncr_updated_at BEFORE UPDATE ON public.audit_ncr FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: audit_visits update_audit_visits_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_audit_visits_updated_at BEFORE UPDATE ON public.audit_visits FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: certificate_risk_alerts update_certificate_risk_alerts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_certificate_risk_alerts_updated_at BEFORE UPDATE ON public.certificate_risk_alerts FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: feature_flags update_feature_flags_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_feature_flags_updated_at BEFORE UPDATE ON public.feature_flags FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: halal_certificates update_halal_certificates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_halal_certificates_updated_at BEFORE UPDATE ON public.halal_certificates FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: materials update_materials_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_materials_updated_at BEFORE UPDATE ON public.materials FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: process_templates update_process_templates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_process_templates_updated_at BEFORE UPDATE ON public.process_templates FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: production_batches update_production_batches_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_production_batches_updated_at BEFORE UPDATE ON public.production_batches FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: submission_evaluations update_submission_evaluations_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_submission_evaluations_updated_at BEFORE UPDATE ON public.submission_evaluations FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: supplier_eligibilities update_supplier_eligibilities_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_supplier_eligibilities_updated_at BEFORE UPDATE ON public.supplier_eligibilities FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: suppliers update_suppliers_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_suppliers_updated_at BEFORE UPDATE ON public.suppliers FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: tenant_feature_overrides update_tenant_feature_overrides_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_tenant_feature_overrides_updated_at BEFORE UPDATE ON public.tenant_feature_overrides FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: audit_checklist_templates audit_checklist_templates_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_checklist_templates
    ADD CONSTRAINT audit_checklist_templates_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.users(id);


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: audit_ncr audit_ncr_closed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_ncr
    ADD CONSTRAINT audit_ncr_closed_by_fkey FOREIGN KEY (closed_by) REFERENCES public.users(id);


--
-- Name: audit_ncr audit_ncr_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_ncr
    ADD CONSTRAINT audit_ncr_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.audit_visit_items(id);


--
-- Name: audit_ncr audit_ncr_visit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_ncr
    ADD CONSTRAINT audit_ncr_visit_id_fkey FOREIGN KEY (visit_id) REFERENCES public.audit_visits(id) ON DELETE CASCADE;


--
-- Name: audit_visit_items audit_visit_items_visit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_visit_items
    ADD CONSTRAINT audit_visit_items_visit_id_fkey FOREIGN KEY (visit_id) REFERENCES public.audit_visits(id) ON DELETE CASCADE;


--
-- Name: audit_visits audit_visits_auditor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_visits
    ADD CONSTRAINT audit_visits_auditor_id_fkey FOREIGN KEY (auditor_id) REFERENCES public.users(id);


--
-- Name: audit_visits audit_visits_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_visits
    ADD CONSTRAINT audit_visits_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.users(id);


--
-- Name: audit_visits audit_visits_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_visits
    ADD CONSTRAINT audit_visits_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.audit_checklist_templates(id);


--
-- Name: batch_anchor_proofs batch_anchor_proofs_anchor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_anchor_proofs
    ADD CONSTRAINT batch_anchor_proofs_anchor_id_fkey FOREIGN KEY (anchor_id) REFERENCES public.blockchain_anchors(id) ON DELETE CASCADE;


--
-- Name: batch_anchor_proofs batch_anchor_proofs_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_anchor_proofs
    ADD CONSTRAINT batch_anchor_proofs_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.production_batches(id) ON DELETE CASCADE;


--
-- Name: batch_materials batch_materials_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_materials
    ADD CONSTRAINT batch_materials_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.production_batches(id) ON DELETE CASCADE;


--
-- Name: batch_materials batch_materials_eligibility_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_materials
    ADD CONSTRAINT batch_materials_eligibility_id_fkey FOREIGN KEY (eligibility_id) REFERENCES public.supplier_eligibilities(id) ON DELETE SET NULL;


--
-- Name: batch_materials batch_materials_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_materials
    ADD CONSTRAINT batch_materials_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.materials(id);


--
-- Name: batch_materials batch_materials_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_materials
    ADD CONSTRAINT batch_materials_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE SET NULL;


--
-- Name: batch_steps batch_steps_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_steps
    ADD CONSTRAINT batch_steps_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.production_batches(id) ON DELETE CASCADE;


--
-- Name: blockchain_anchors blockchain_anchors_parent_anchor_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.blockchain_anchors
    ADD CONSTRAINT blockchain_anchors_parent_anchor_fkey FOREIGN KEY (parent_anchor) REFERENCES public.blockchain_anchors(id) ON DELETE SET NULL;


--
-- Name: cert_anchor_proofs cert_anchor_proofs_anchor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cert_anchor_proofs
    ADD CONSTRAINT cert_anchor_proofs_anchor_id_fkey FOREIGN KEY (anchor_id) REFERENCES public.blockchain_anchors(id) ON DELETE CASCADE;


--
-- Name: cert_anchor_proofs cert_anchor_proofs_cert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cert_anchor_proofs
    ADD CONSTRAINT cert_anchor_proofs_cert_id_fkey FOREIGN KEY (cert_id) REFERENCES public.halal_certificates(id) ON DELETE CASCADE;


--
-- Name: certificate_risk_alerts certificate_risk_alerts_certificate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_risk_alerts
    ADD CONSTRAINT certificate_risk_alerts_certificate_id_fkey FOREIGN KEY (certificate_id) REFERENCES public.supplier_eligibilities(id) ON DELETE CASCADE;


--
-- Name: certificate_risk_alerts certificate_risk_alerts_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_risk_alerts
    ADD CONSTRAINT certificate_risk_alerts_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE CASCADE;


--
-- Name: deletion_tokens deletion_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deletion_tokens
    ADD CONSTRAINT deletion_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: documents documents_approver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_approver_id_fkey FOREIGN KEY (approver_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: documents documents_dossier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_dossier_id_fkey FOREIGN KEY (dossier_id) REFERENCES public.dossiers(id) ON DELETE SET NULL;


--
-- Name: documents documents_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: documents documents_superseded_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_superseded_by_id_fkey FOREIGN KEY (superseded_by_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: documents documents_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: documents documents_version_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_version_parent_id_fkey FOREIGN KEY (version_parent_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: dossiers dossiers_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dossiers
    ADD CONSTRAINT dossiers_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: dossiers dossiers_standard_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dossiers
    ADD CONSTRAINT dossiers_standard_type_id_fkey FOREIGN KEY (standard_type_id) REFERENCES public.standard_types(id) ON DELETE SET NULL;


--
-- Name: halal_certificates halal_certificates_issued_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.halal_certificates
    ADD CONSTRAINT halal_certificates_issued_by_fkey FOREIGN KEY (issued_by) REFERENCES public.users(id);


--
-- Name: halal_certificates halal_certificates_revoked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.halal_certificates
    ADD CONSTRAINT halal_certificates_revoked_by_fkey FOREIGN KEY (revoked_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: halal_certificates halal_certificates_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.halal_certificates
    ADD CONSTRAINT halal_certificates_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON DELETE CASCADE;


--
-- Name: industry_schemas industry_schemas_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.industry_schemas
    ADD CONSTRAINT industry_schemas_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: industry_standards industry_standards_industry_schema_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.industry_standards
    ADD CONSTRAINT industry_standards_industry_schema_id_fkey FOREIGN KEY (industry_schema_id) REFERENCES public.industry_schemas(id) ON DELETE CASCADE;


--
-- Name: industry_standards industry_standards_standard_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.industry_standards
    ADD CONSTRAINT industry_standards_standard_type_id_fkey FOREIGN KEY (standard_type_id) REFERENCES public.standard_types(id) ON DELETE CASCADE;


--
-- Name: materials materials_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materials
    ADD CONSTRAINT materials_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);


--
-- Name: member_invites member_invites_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.member_invites
    ADD CONSTRAINT member_invites_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: production_batches production_batches_process_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.production_batches
    ADD CONSTRAINT production_batches_process_template_id_fkey FOREIGN KEY (process_template_id) REFERENCES public.process_templates(id);


--
-- Name: push_subscriptions push_subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: schema_doc_types schema_doc_types_schema_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_doc_types
    ADD CONSTRAINT schema_doc_types_schema_id_fkey FOREIGN KEY (schema_id) REFERENCES public.industry_schemas(id) ON DELETE CASCADE;


--
-- Name: standard_doc_types standard_doc_types_standard_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.standard_doc_types
    ADD CONSTRAINT standard_doc_types_standard_type_id_fkey FOREIGN KEY (standard_type_id) REFERENCES public.standard_types(id) ON DELETE CASCADE;


--
-- Name: standard_types standard_types_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.standard_types
    ADD CONSTRAINT standard_types_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: submission_comments submission_comments_author_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_comments
    ADD CONSTRAINT submission_comments_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.users(id);


--
-- Name: submission_comments submission_comments_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_comments
    ADD CONSTRAINT submission_comments_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON DELETE CASCADE;


--
-- Name: submission_evaluations submission_evaluations_auditor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_evaluations
    ADD CONSTRAINT submission_evaluations_auditor_id_fkey FOREIGN KEY (auditor_id) REFERENCES public.users(id);


--
-- Name: submission_evaluations submission_evaluations_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_evaluations
    ADD CONSTRAINT submission_evaluations_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON DELETE CASCADE;


--
-- Name: submission_revision_requests submission_revision_requests_requester_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_revision_requests
    ADD CONSTRAINT submission_revision_requests_requester_id_fkey FOREIGN KEY (requester_id) REFERENCES public.users(id);


--
-- Name: submission_revision_requests submission_revision_requests_submission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submission_revision_requests
    ADD CONSTRAINT submission_revision_requests_submission_id_fkey FOREIGN KEY (submission_id) REFERENCES public.submissions(id) ON DELETE CASCADE;


--
-- Name: submissions submissions_auditor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_auditor_id_fkey FOREIGN KEY (auditor_id) REFERENCES public.users(id);


--
-- Name: submissions submissions_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.submissions
    ADD CONSTRAINT submissions_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.users(id);


--
-- Name: supplier_certificates supplier_certificates_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_certificates
    ADD CONSTRAINT supplier_certificates_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE CASCADE;


--
-- Name: supplier_eligibilities supplier_eligibilities_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_eligibilities
    ADD CONSTRAINT supplier_eligibilities_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: supplier_eligibilities supplier_eligibilities_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_eligibilities
    ADD CONSTRAINT supplier_eligibilities_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: supplier_eligibilities supplier_eligibilities_source_certificate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_eligibilities
    ADD CONSTRAINT supplier_eligibilities_source_certificate_id_fkey FOREIGN KEY (source_certificate_id) REFERENCES public.halal_certificates(id) ON DELETE SET NULL;


--
-- Name: supplier_eligibilities supplier_eligibilities_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_eligibilities
    ADD CONSTRAINT supplier_eligibilities_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE CASCADE;


--
-- Name: supply_relationships supply_relationships_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supply_relationships
    ADD CONSTRAINT supply_relationships_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id) ON DELETE CASCADE;


--
-- Name: tenant_feature_overrides tenant_feature_overrides_feature_name_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_feature_overrides
    ADD CONSTRAINT tenant_feature_overrides_feature_name_fkey FOREIGN KEY (feature_name) REFERENCES public.feature_flags(name) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: users users_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id);


--
-- Name: users users_industry_schema_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_industry_schema_id_fkey FOREIGN KEY (industry_schema_id) REFERENCES public.industry_schemas(id) ON DELETE SET NULL;


--
-- Name: users users_invited_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_invited_by_fkey FOREIGN KEY (invited_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict NotxvhnJ3QRiIiQ5FFZusNJGqUSFiCoqYtoGg2DFieit2T0i9ZxmW1FGOu7hx0A

