import { useEffect, useState } from "react";
import EtiquetasTable from "../components/EtiquetasTable";
import EtiquetaForm from "../components/EtiquetasForm";

const API = "http://localhost:8000/api/etiquetas";

export default function EtiquetasPage() {
  const [etiquetas, setEtiquetas] = useState([]);
  const [editando, setEditando] = useState(null);

  async function cargarEtiquetas() {
    const res = await fetch(API);
    const data = await res.json();
    setEtiquetas(data);
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
    if (!window.confirm(`Eliminar ${nombre}?`)) return;

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
    <div style={{ padding: 30 }}>
      <h1>Administración de etiquetas</h1>

      <EtiquetaForm
        onGuardar={guardar}
        etiquetaEditar={editando}
        cancelar={() => setEditando(null)}
      />

      <EtiquetasTable
        etiquetas={etiquetas}
        onEditar={setEditando}
        onEliminar={eliminar}
        onReordenar={reordenar}
      />
    </div>
  );
}