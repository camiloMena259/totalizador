import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import './tablas.css';

function FilaEtiqueta({ etiqueta, onEditar, onEliminar }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: etiqueta.etiqueta });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    background: isDragging ? "#FAFBFC" : undefined,
  };

  return (
    <tr ref={setNodeRef} style={style}>
      <td
        {...attributes}
        {...listeners}
        className="celda-arrastre"
        title="Arrastrar para cambiar prioridad"
      >
        ⠿
      </td>

      <td>
        <span className="badge-etiqueta">{etiqueta.etiqueta}</span>
      </td>

      <td className="celda-palabras">{etiqueta.palabras_clave.join(", ")}</td>

      <td className="celda-acciones">
        <button className="btn btn-secondary btn-sm" onClick={() => onEditar(etiqueta)}>
          Editar
        </button>
        <button className="btn btn-danger-text btn-sm" onClick={() => onEliminar(etiqueta.etiqueta)}>
          Eliminar
        </button>
      </td>
    </tr>
  );
}

export default function EtiquetasTable({
  etiquetas,
  onEditar,
  onEliminar,
  onReordenar,
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 }, // evita drags accidentales al hacer click
    })
  );

  function handleDragEnd(event) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = etiquetas.findIndex((e) => e.etiqueta === active.id);
    const newIndex = etiquetas.findIndex((e) => e.etiqueta === over.id);

    onReordenar(arrayMove(etiquetas, oldIndex, newIndex));
  }

  if (etiquetas.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-state__icon">🏷️</span>
        <strong>Todavía no creaste etiquetas</strong>
        <span>Usá el formulario de arriba para crear la primera. Las etiquetas se usan para clasificar automáticamente los movimientos.</span>
      </div>
    );
  }

  return (
    <div className="tablas-scope">
      <div className="tabla-card">
        <div className="tabla-header">
          <h2 className="tabla-titulo">
            Etiquetas configuradas
            <span className="conteo">{etiquetas.length}</span>
          </h2>
          <p className="tabla-hint">
            La fila más arriba tiene mayor prioridad: si un concepto matchea varias etiquetas, gana la que esté más arriba.
          </p>
        </div>

        <div className="tabla-wrapper">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <table className="tabla">
              <thead>
                <tr>
                  <th></th>
                  <th>Etiqueta</th>
                  <th>Palabras clave</th>
                  <th>Acciones</th>
                </tr>
              </thead>

              <tbody>
                <SortableContext
                  items={etiquetas.map((e) => e.etiqueta)}
                  strategy={verticalListSortingStrategy}
                >
                  {etiquetas.map((e) => (
                    <FilaEtiqueta
                      key={e.etiqueta}
                      etiqueta={e}
                      onEditar={onEditar}
                      onEliminar={onEliminar}
                    />
                  ))}
                </SortableContext>
              </tbody>
            </table>
          </DndContext>
        </div>
      </div>
    </div>
  );
}
