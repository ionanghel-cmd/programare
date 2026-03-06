import csv
import io
import sqlite3
from contextlib import closing
from datetime import date, datetime, time
from typing import Dict, List, Optional

import streamlit as st

DB_NAME = "programari.db"


# -----------------------------
# Database layer
# -----------------------------
def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with rows accessible like dicts."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create table if it does not already exist."""
    query = """
    CREATE TABLE IF NOT EXISTS programari (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_programare TEXT NOT NULL,
        ora_programare TEXT NOT NULL,
        client TEXT NOT NULL,
        telefon TEXT,
        vehicul TEXT NOT NULL,
        interventie TEXT NOT NULL,
        observatii TEXT,
        created_at TEXT NOT NULL
    )
    """
    with closing(get_connection()) as conn:
        conn.execute(query)
        conn.commit()


def add_programare(
    data_programare: str,
    ora_programare: str,
    client: str,
    telefon: str,
    vehicul: str,
    interventie: str,
    observatii: str,
) -> bool:
    """Insert appointment if duplicate does not exist. Returns True on success."""
    duplicate_query = """
    SELECT id FROM programari
    WHERE data_programare = ? AND ora_programare = ? AND lower(trim(client)) = lower(trim(?))
    LIMIT 1
    """
    insert_query = """
    INSERT INTO programari (
        data_programare, ora_programare, client, telefon, vehicul, interventie, observatii, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    with closing(get_connection()) as conn:
        duplicate = conn.execute(
            duplicate_query, (data_programare, ora_programare, client)
        ).fetchone()
        if duplicate:
            return False

        conn.execute(
            insert_query,
            (
                data_programare,
                ora_programare,
                client.strip(),
                telefon.strip(),
                vehicul.strip(),
                interventie.strip(),
                observatii.strip(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    return True


def get_programari(
    zi_selectata: str,
    client_q: str = "",
    telefon_q: str = "",
    vehicul_q: str = "",
) -> List[sqlite3.Row]:
    """Fetch appointments filtered by date and optional search inputs."""
    query = """
    SELECT * FROM programari
    WHERE data_programare = ?
      AND client LIKE ?
      AND COALESCE(telefon, '') LIKE ?
      AND vehicul LIKE ?
    ORDER BY ora_programare ASC, id ASC
    """

    with closing(get_connection()) as conn:
        rows = conn.execute(
            query,
            (
                zi_selectata,
                f"%{client_q.strip()}%",
                f"%{telefon_q.strip()}%",
                f"%{vehicul_q.strip()}%",
            ),
        ).fetchall()
    return rows


def update_programare(
    programare_id: int,
    data_programare: str,
    ora_programare: str,
    client: str,
    telefon: str,
    vehicul: str,
    interventie: str,
    observatii: str,
) -> bool:
    """Update appointment. Returns False if duplicate conflict is found."""
    duplicate_query = """
    SELECT id FROM programari
    WHERE data_programare = ? AND ora_programare = ?
      AND lower(trim(client)) = lower(trim(?))
      AND id != ?
    LIMIT 1
    """
    update_query = """
    UPDATE programari
    SET data_programare = ?,
        ora_programare = ?,
        client = ?,
        telefon = ?,
        vehicul = ?,
        interventie = ?,
        observatii = ?
    WHERE id = ?
    """

    with closing(get_connection()) as conn:
        duplicate = conn.execute(
            duplicate_query,
            (data_programare, ora_programare, client, programare_id),
        ).fetchone()
        if duplicate:
            return False

        conn.execute(
            update_query,
            (
                data_programare,
                ora_programare,
                client.strip(),
                telefon.strip(),
                vehicul.strip(),
                interventie.strip(),
                observatii.strip(),
                programare_id,
            ),
        )
        conn.commit()
    return True


def delete_programare(programare_id: int) -> None:
    """Delete appointment by ID."""
    with closing(get_connection()) as conn:
        conn.execute("DELETE FROM programari WHERE id = ?", (programare_id,))
        conn.commit()


def duplicate_programare(
    original_id: int,
    data_programare: str,
    ora_programare: str,
) -> bool:
    """Duplicate an appointment to another slot. Returns False on conflict/missing."""
    select_query = "SELECT * FROM programari WHERE id = ?"

    with closing(get_connection()) as conn:
        original = conn.execute(select_query, (original_id,)).fetchone()
        if not original:
            return False

    return add_programare(
        data_programare=data_programare,
        ora_programare=ora_programare,
        client=original["client"],
        telefon=original["telefon"] or "",
        vehicul=original["vehicul"],
        interventie=original["interventie"],
        observatii=original["observatii"] or "",
    )


def export_programari_csv(rows: List[sqlite3.Row]) -> bytes:
    """Build CSV bytes from current filtered rows."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "ID",
            "Data",
            "Ora",
            "Client",
            "Telefon",
            "Vehicul",
            "Intervenție",
            "Observații",
            "Creat la",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["data_programare"],
                row["ora_programare"],
                row["client"],
                row["telefon"] or "",
                row["vehicul"],
                row["interventie"],
                row["observatii"] or "",
                row["created_at"],
            ]
        )

    return buffer.getvalue().encode("utf-8-sig")


# -----------------------------
# UI helpers
# -----------------------------
def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .subtitle {
            color: #5b6475;
            margin-top: -6px;
            margin-bottom: 1rem;
            font-size: 0.98rem;
        }
        .appt-card {
            border: 1px solid #e7ebf3;
            border-radius: 14px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.85rem;
            background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
        }
        .appt-time {
            font-size: 1.2rem;
            font-weight: 700;
            color: #0d47a1;
            margin-bottom: 0.25rem;
        }
        .appt-main {
            font-weight: 600;
            font-size: 1.02rem;
            margin-bottom: 0.2rem;
        }
        .appt-meta {
            color: #4f5d75;
            font-size: 0.92rem;
            margin-bottom: 0.1rem;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def validate_required_fields(payload: Dict[str, str]) -> Optional[str]:
    required_labels = {
        "data_programare": "Data",
        "ora_programare": "Ora",
        "client": "Nume client",
        "vehicul": "Vehicul",
        "interventie": "Tip intervenție",
    }
    for key, label in required_labels.items():
        if not str(payload.get(key, "")).strip():
            return f"Câmpul „{label}” este obligatoriu."
    return None


def render_new_appointment_tab() -> None:
    st.subheader("Programare nouă")
    st.caption("Completează câmpurile esențiale și salvează în câteva secunde.")

    with st.container(border=True):
        with st.form("new_appointment_form", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                data_programare = st.date_input("Data programării", value=date.today(), format="DD.MM.YYYY")
            with col2:
                ora_programare = st.time_input("Ora programării", value=time(9, 0), step=1800)

            col3, col4 = st.columns([2, 1])
            with col3:
                client = st.text_input("Nume client *", placeholder="Ex: Popescu Andrei")
            with col4:
                telefon = st.text_input("Telefon", placeholder="Ex: 07xx xxx xxx")

            vehicul = st.text_input("Vehicul *", placeholder="Ex: Yamaha Grizzly 700")
            interventie = st.text_input("Tip intervenție *", placeholder="Ex: Revizie periodică")
            observatii = st.text_area(
                "Observații scurte (opțional)",
                placeholder="Detalii utile pentru recepție...",
                height=90,
            )

            submitted = st.form_submit_button("💾 Salvează programarea", use_container_width=True)

            if submitted:
                payload = {
                    "data_programare": data_programare.isoformat(),
                    "ora_programare": ora_programare.strftime("%H:%M"),
                    "client": client,
                    "telefon": telefon,
                    "vehicul": vehicul,
                    "interventie": interventie,
                    "observatii": observatii,
                }
                validation_error = validate_required_fields(payload)
                if validation_error:
                    st.error(validation_error)
                else:
                    ok = add_programare(**payload)
                    if ok:
                        st.success("Programarea a fost salvată cu succes.")
                    else:
                        st.warning(
                            "Există deja o programare cu aceeași dată, oră și client."
                        )


def render_programare_card(programare: sqlite3.Row) -> None:
    pid = int(programare["id"])
    st.markdown(
        f"""
        <div class="appt-card">
            <div class="appt-time">🕒 {programare['ora_programare']}</div>
            <div class="appt-main">{programare['client']} · {programare['vehicul']}</div>
            <div class="appt-meta"><strong>Telefon:</strong> {programare['telefon'] or '-'}</div>
            <div class="appt-meta"><strong>Intervenție:</strong> {programare['interventie']}</div>
            <div class="appt-meta"><strong>Observații:</strong> {programare['observatii'] or '-'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        if st.button("✏️ Editează", key=f"edit_btn_{pid}", use_container_width=True):
            st.session_state[f"edit_{pid}"] = not st.session_state.get(f"edit_{pid}", False)
            st.session_state[f"dup_{pid}"] = False
            st.session_state[f"del_{pid}"] = False
    with b2:
        if st.button("📄 Duplică", key=f"dup_btn_{pid}", use_container_width=True):
            st.session_state[f"dup_{pid}"] = not st.session_state.get(f"dup_{pid}", False)
            st.session_state[f"edit_{pid}"] = False
            st.session_state[f"del_{pid}"] = False
    with b3:
        if st.button("🗑️ Șterge", key=f"del_btn_{pid}", use_container_width=True):
            st.session_state[f"del_{pid}"] = not st.session_state.get(f"del_{pid}", False)
            st.session_state[f"edit_{pid}"] = False
            st.session_state[f"dup_{pid}"] = False

    if st.session_state.get(f"edit_{pid}", False):
        with st.container(border=True):
            st.markdown("**Editare programare**")
            with st.form(f"edit_form_{pid}"):
                c1, c2 = st.columns(2)
                with c1:
                    data_edit = st.date_input(
                        "Data",
                        value=datetime.strptime(programare["data_programare"], "%Y-%m-%d").date(),
                        key=f"edit_date_{pid}",
                        format="DD.MM.YYYY",
                    )
                with c2:
                    ora_edit = st.time_input(
                        "Ora",
                        value=datetime.strptime(programare["ora_programare"], "%H:%M").time(),
                        key=f"edit_time_{pid}",
                        step=1800,
                    )

                client_edit = st.text_input("Client", value=programare["client"], key=f"edit_client_{pid}")
                telefon_edit = st.text_input("Telefon", value=programare["telefon"] or "", key=f"edit_tel_{pid}")
                vehicul_edit = st.text_input("Vehicul", value=programare["vehicul"], key=f"edit_veh_{pid}")
                interventie_edit = st.text_input(
                    "Intervenție", value=programare["interventie"], key=f"edit_int_{pid}"
                )
                observatii_edit = st.text_area(
                    "Observații",
                    value=programare["observatii"] or "",
                    key=f"edit_obs_{pid}",
                    height=80,
                )

                save_edit = st.form_submit_button("Salvează modificările", use_container_width=True)
                if save_edit:
                    payload = {
                        "data_programare": data_edit.isoformat(),
                        "ora_programare": ora_edit.strftime("%H:%M"),
                        "client": client_edit,
                        "telefon": telefon_edit,
                        "vehicul": vehicul_edit,
                        "interventie": interventie_edit,
                        "observatii": observatii_edit,
                    }
                    validation_error = validate_required_fields(payload)
                    if validation_error:
                        st.error(validation_error)
                    else:
                        ok = update_programare(pid, **payload)
                        if ok:
                            st.success("Programarea a fost actualizată.")
                            st.session_state[f"edit_{pid}"] = False
                            st.rerun()
                        else:
                            st.warning(
                                "Nu s-a salvat: există deja o programare identică (data, ora, client)."
                            )

    if st.session_state.get(f"dup_{pid}", False):
        with st.container(border=True):
            st.markdown("**Duplicare rapidă**")
            with st.form(f"dup_form_{pid}"):
                c1, c2 = st.columns(2)
                with c1:
                    new_date = st.date_input(
                        "Data nouă",
                        value=datetime.strptime(programare["data_programare"], "%Y-%m-%d").date(),
                        key=f"dup_date_{pid}",
                        format="DD.MM.YYYY",
                    )
                with c2:
                    new_time = st.time_input(
                        "Ora nouă",
                        value=datetime.strptime(programare["ora_programare"], "%H:%M").time(),
                        key=f"dup_time_{pid}",
                        step=1800,
                    )

                do_duplicate = st.form_submit_button("Creează copia", use_container_width=True)
                if do_duplicate:
                    ok = duplicate_programare(
                        original_id=pid,
                        data_programare=new_date.isoformat(),
                        ora_programare=new_time.strftime("%H:%M"),
                    )
                    if ok:
                        st.success("Programarea a fost duplicată.")
                        st.session_state[f"dup_{pid}"] = False
                        st.rerun()
                    else:
                        st.warning(
                            "Copierea nu a fost făcută: există deja o programare identică sau originalul lipsește."
                        )

    if st.session_state.get(f"del_{pid}", False):
        with st.container(border=True):
            st.error("Confirmi ștergerea acestei programări?")
            d1, d2 = st.columns(2)
            with d1:
                if st.button("✅ Confirm ștergerea", key=f"confirm_del_{pid}", use_container_width=True):
                    delete_programare(pid)
                    st.success("Programarea a fost ștearsă.")
                    st.session_state[f"del_{pid}"] = False
                    st.rerun()
            with d2:
                if st.button("Renunță", key=f"cancel_del_{pid}", use_container_width=True):
                    st.session_state[f"del_{pid}"] = False
                    st.rerun()

    st.divider()


def render_agenda_tab() -> None:
    st.subheader("Programări")

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1, 1, 1, 1])
    with filter_col1:
        selected_date = st.date_input(
            "Ziua",
            value=st.session_state.get("selected_date", date.today()),
            key="selected_date",
            format="DD.MM.YYYY",
        )
    with filter_col2:
        client_q = st.text_input("Caută client", placeholder="Nume client")
    with filter_col3:
        telefon_q = st.text_input("Caută telefon", placeholder="07xx...")
    with filter_col4:
        vehicul_q = st.text_input("Caută vehicul", placeholder="Model vehicul")

    rows = get_programari(
        zi_selectata=selected_date.isoformat(),
        client_q=client_q,
        telefon_q=telefon_q,
        vehicul_q=vehicul_q,
    )

    csv_bytes = export_programari_csv(rows)
    st.download_button(
        "⬇️ Export CSV (filtrate)",
        data=csv_bytes,
        file_name=f"programari_{selected_date.isoformat()}.csv",
        mime="text/csv",
        use_container_width=False,
    )

    st.caption(f"Rezultate: {len(rows)} programare/programări")
    st.divider()

    if not rows:
        st.info("Nu există programări pentru această zi.")
        return

    for row in rows:
        render_programare_card(row)


def main() -> None:
    st.set_page_config(
        page_title="Programări Service Moto / ATV",
        page_icon="🛠️",
        layout="wide",
    )

    init_db()
    inject_styles()

    st.title("Programări Service Moto / ATV")
    st.markdown(
        '<p class="subtitle">Panou simplu pentru planificarea rapidă a programărilor</p>',
        unsafe_allow_html=True,
    )

    tab_new, tab_list = st.tabs(["Programare nouă", "Programări"])

    with tab_new:
        render_new_appointment_tab()

    with tab_list:
        render_agenda_tab()


if __name__ == "__main__":
    main()
