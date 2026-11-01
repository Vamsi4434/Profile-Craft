"""Profile Craft — Streamlit UI.

The UI is intentionally thin: validation lives in ``profile_craft.models``,
persistence in ``profile_craft.db``, and analytics in ``profile_craft.analytics``.
Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st
from pydantic import ValidationError

from profile_craft import analytics, db
from profile_craft.models import Certification, Education, Experience, Profile
from profile_craft.pdf import generate_ats_pdf

st.set_page_config(page_title="Profile Craft", page_icon="📝", layout="wide")


@st.cache_resource
def get_conn():
    conn = db.connect()
    db.init_db(conn)
    return conn


conn = get_conn()
st.session_state.setdefault("user_id", None)
st.session_state.setdefault("username", "")


def show_validation_errors(exc: ValidationError) -> None:
    for err in exc.errors():
        field = " → ".join(str(p) for p in err["loc"])
        st.error(f"**{field}**: {err['msg']}")


# ---------------------------------------------------------------- auth

def auth_page() -> None:
    st.markdown("<h1 style='text-align:center'>💼 Profile Craft</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center'>Build an ATS-friendly resume backed by a validated data store.</p>",
        unsafe_allow_html=True,
    )
    _, col, _ = st.columns([1, 2, 1])
    with col:
        login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
        with login_tab:
            user = st.text_input("Username / email", key="login_user")
            pw = st.text_input("Password", type="password", key="login_pw")
            if st.button("Log in", type="primary", use_container_width=True):
                user_id = db.authenticate(conn, user, pw)
                if user_id:
                    st.session_state.update(user_id=user_id, username=user.strip())
                    st.rerun()
                st.error("Invalid username or password.")
        with signup_tab:
            user = st.text_input("Choose a username", key="su_user")
            pw = st.text_input("Choose a password", type="password", key="su_pw")
            pw2 = st.text_input("Confirm password", type="password", key="su_pw2")
            if st.button("Create account", use_container_width=True):
                if not user.strip() or not pw:
                    st.error("Username and password are required.")
                elif len(pw) < 8:
                    st.error("Password must be at least 8 characters.")
                elif pw != pw2:
                    st.error("Passwords do not match.")
                else:
                    try:
                        db.create_user(conn, user, pw)
                        st.success("Account created. You can log in now.")
                    except db.UserExistsError:
                        st.error("That username is already taken.")


# ---------------------------------------------------------------- edit

def _rows(key: str, existing: list, fields: list[tuple[str, str]]) -> list[dict]:
    """Render a repeatable group of inputs and return the non-empty rows."""
    count_key = f"{key}_count"
    st.session_state.setdefault(count_key, max(1, len(existing)))
    rows = []
    for i in range(st.session_state[count_key]):
        current = existing[i] if i < len(existing) else {}
        cols = st.columns(len(fields))
        row = {}
        for col, (name, label) in zip(cols, fields, strict=True):
            with col:
                val = current.get(name)
                row[name] = st.text_input(f"{label} #{i + 1}", value="" if val is None else str(val), key=f"{key}_{name}_{i}")
        if any(v.strip() for v in row.values()):
            rows.append(row)
    if st.button(f"➕ Add {key}", key=f"add_{key}"):
        st.session_state[count_key] += 1
        st.rerun()
    return rows


def edit_page(profile: Profile) -> None:
    st.title("📝 Edit profile")
    data = profile.model_dump()

    st.subheader("Personal details")
    c1, c2 = st.columns(2)
    full_name = c1.text_input("Full name", data["full_name"])
    email = c1.text_input("Email", data["email"])
    phone = c2.text_input("Phone", data["phone"])
    location = c2.text_input("Location (City, State)", data["location"])
    summary = st.text_area("Professional summary", data["summary"])

    st.subheader("Education")
    education = _rows("education", data["education"],
                      [("school", "School"), ("degree", "Degree"), ("graduation_year", "Graduation year")])

    st.subheader("Experience")
    experience = _rows("experience", data["experience"],
                       [("company", "Company"), ("role", "Role"), ("start_year", "Start year"), ("end_year", "End year (blank = present)")])
    for i, x in enumerate(experience):
        prior = data["experience"][i]["description"] if i < len(data["experience"]) else ""
        x["description"] = st.text_area(f"Description for {x.get('role') or 'role'} #{i + 1}", prior, key=f"exp_desc_{i}")
        for k in ("start_year", "end_year"):
            x[k] = x[k].strip() or None

    st.subheader("Certifications & skills")
    certs = _rows("certification", data["certifications"], [("name", "Certification / skill")])

    if st.button("💾 Save profile", type="primary", use_container_width=True):
        try:
            new_profile = Profile(
                full_name=full_name, email=email, phone=phone, location=location, summary=summary,
                education=[Education(**e) for e in education],
                experience=[Experience(**x) for x in experience],
                certifications=[Certification(**c) for c in certs],
            )
        except ValidationError as exc:
            show_validation_errors(exc)
            return
        db.save_profile(conn, st.session_state.user_id, new_profile)
        st.success("Profile saved.")


# ---------------------------------------------------------------- view

def view_page(profile: Profile) -> None:
    st.title("👀 Resume preview")
    if not profile.full_name:
        st.warning("Add your name in **Edit profile** first.")
        return
    st.progress(profile.completeness(), text=f"Profile {profile.completeness():.0%} complete")
    with st.container(border=True):
        st.header(profile.full_name)
        st.caption(" | ".join(x for x in (profile.phone, profile.email, profile.location) if x))
        if profile.summary:
            st.subheader("Summary")
            st.write(profile.summary)
        if profile.experience:
            st.subheader("Experience")
            for x in profile.experience:
                st.markdown(f"**{x.role}** — *{x.company}* ({x.duration})")
                st.write(x.description)
        if profile.education:
            st.subheader("Education")
            for e in profile.education:
                st.markdown(f"**{e.degree}** — *{e.school}* ({e.graduation_year or ''})")
        if profile.certifications:
            st.subheader("Certifications & skills")
            st.write(" • ".join(c.name for c in profile.certifications))

    st.download_button(
        "📥 Download ATS resume (PDF)",
        data=generate_ats_pdf(profile),
        file_name=f"{profile.full_name.replace(' ', '_')}_Resume.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )


# ---------------------------------------------------------------- insights

def insights_page() -> None:
    st.title("📊 Data insights")
    st.caption("Aggregate SQL analytics across all profiles in the database.")
    comp = analytics.profile_completeness(conn)
    m1, m2, m3 = st.columns(3)
    m1.metric("Profiles", len(comp))
    m2.metric("Avg completeness", f"{comp['completeness_pct'].mean():.0f}%" if len(comp) else "—")
    m3.metric("ETL runs", len(analytics.etl_runs(conn)))

    st.subheader("Profile completeness")
    st.dataframe(comp, use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Top certifications")
        certs = analytics.top_certifications(conn)
        if len(certs):
            st.bar_chart(certs, x="certification", y="users")
    with right:
        st.subheader("Years of experience")
        st.dataframe(analytics.experience_years(conn), use_container_width=True, hide_index=True)

    st.subheader("Pipeline run history")
    st.dataframe(analytics.etl_runs(conn), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------- router

if st.session_state.user_id is None:
    auth_page()
else:
    st.sidebar.title("🛠️ Profile Craft")
    st.sidebar.write(f"Signed in as **{st.session_state.username}**")
    page = st.sidebar.radio("Navigate", ["📝 Edit profile", "👀 Preview & export", "📊 Insights"])
    if st.sidebar.button("Log out", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    current = db.get_profile(conn, st.session_state.user_id)
    if page.startswith("📝"):
        edit_page(current)
    elif page.startswith("👀"):
        view_page(current)
    else:
        insights_page()
