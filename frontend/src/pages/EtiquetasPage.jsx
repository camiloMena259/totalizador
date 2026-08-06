import { useEffect, useState } from "react";
import EtiquetasTable from "../components/EtiquetasTable";
import EtiquetaForm from "../components/EtiquetasForm";
import "./etiquetas.css";

const API = "http://localhost:8000/api/etiquetas";

export default function EtiquetasPage() {
  const [etiquetas, setEtiquetas] = useState([]);
  const [editando, setEditando] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  async function cargarEtiquetas() {
    setCargando(true);
    setError(null);
    try {
      const res = await fetch(API);
      if (!res.ok) throw new Error("No se pudieron cargar las etiquetas.");
      const data = await res.json();
      setEtiquetas(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    cargarEtiquetas();
  }, []);

  async function guardar(datos) {
    if (editando) {
      await fetch(`${API}/${editando.etiqueta}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nuevo_nombre: datos.etiqueta,
          palabras_clave: datos.palabras_clave,
        }),
      });
    } else {
      await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(datos),
      });
    }

    setEditando(null);
    cargarEtiquetas();
  }

  async function eliminar(nombre) {
    if (!window.confirm(`¿Eliminar la etiqueta "${nombre}"?`)) return;

    await fetch(`${API}/${nombre}`, { method: "DELETE" });
    cargarEtiquetas();
  }

  async function reordenar(nuevaLista) {
    const anterior = etiquetas;
    setEtiquetas(nuevaLista); // optimista: se ve el cambio al instante

    try {
      const res = await fetch(`${API}/reordenar`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          orden: nuevaLista.map((e) => e.etiqueta),
        }),
      });

      if (!res.ok) throw new Error("No se pudo guardar el nuevo orden");
    } catch (err) {
      console.error(err);
      alert("No se pudo guardar el nuevo orden, se revierte el cambio.");
      setEtiquetas(anterior); // rollback si falla el backend
    }
  }

  return (
    <div className="etiquetas-page">
      <section className="card">
        <div className="card__header">
          <h2 className="card__title">
            {editando ? "Editar etiqueta" : "Nueva etiqueta"}
          </h2>
          {!editando && (
            <p className="card__hint">Se aplican por orden de prioridad al totalizar un extracto.</p>
          )}
        </div>

        <EtiquetaForm
          onGuardar={guardar}
          etiquetaEditar={editando}
          cancelar={() => setEditando(null)}
        />
      </section>

      {error && (
        <div className="alert alert-error" role="alert">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {cargando ? (
        <div className="empty-state" style={{ marginTop: 20 }}>
          <span className="spinner spinner-dark" />
          <span style={{ marginTop: 8 }}>Cargando etiquetas…</span>
        </div>
      ) : (
        <EtiquetasTable
          etiquetas={etiquetas}
          onEditar={setEditando}
          onEliminar={eliminar}
          onReordenar={reordenar}
        />
      )}
    </div>
  );
}
