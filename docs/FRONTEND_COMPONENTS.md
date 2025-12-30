# Frontend Component Architecture

## Attachment & Preview System

```
┌─────────────────────────────────────────────────────────────────┐
│ Page (Verifications.tsx / Invoices.tsx)                         │
│                                                                 │
│  State:                                                         │
│  ├─ formAttachments[]         ← synced from AttachmentManager   │
│  └─ pendingAttachmentIds[]    ← lifted to survive remounts      │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ useAttachmentPreviewController(formAttachments)           │  │
│  │                                                           │  │
│  │  Returns:                                                 │  │
│  │  ├─ selectedIndex, previewUrl, isPinned                  │  │
│  │  ├─ openPreview(index), closePreview(), togglePinned()   │  │
│  │  ├─ floatingPreview   → renders AttachmentPreviewPanel   │  │
│  │  └─ pinnedPreview     → renders inline preview content   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ DraggableModal                                            │  │
│  │  Props: isPinned, rightPanel={pinnedPreview}              │  │
│  │                                                           │  │
│  │  Layouts:                                                 │  │
│  │  ├─ Floating  → draggable, resizable window              │  │
│  │  ├─ Maximized → fullscreen                               │  │
│  │  └─ Pinned    → 50/50 split-view with rightPanel         │  │
│  │                                                           │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │ Form (VerificationForm / InvoiceForm)               │ │  │
│  │  │                                                     │ │  │
│  │  │  Props:                                             │ │  │
│  │  │  ├─ pendingAttachmentIds (controlled)              │ │  │
│  │  │  ├─ onPendingAttachmentIdsChange                   │ │  │
│  │  │  ├─ onAttachmentsChange → setFormAttachments       │ │  │
│  │  │  └─ onAttachmentClick → openPreview(index)         │ │  │
│  │  │                                                     │ │  │
│  │  │  ┌───────────────────────────────────────────────┐ │ │  │
│  │  │  │ AttachmentManager                             │ │ │  │
│  │  │  │                                               │ │ │  │
│  │  │  │  Computed:                                    │ │ │  │
│  │  │  │  └─ visibleAttachments (from pendingIds)     │ │ │  │
│  │  │  │                                               │ │ │  │
│  │  │  │  Callbacks:                                   │ │ │  │
│  │  │  │  ├─ onVisibleAttachmentsChange (guarded)     │ │ │  │
│  │  │  │  └─ onAttachmentClick                        │ │ │  │
│  │  │  └───────────────────────────────────────────────┘ │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  {floatingPreview}  ← rendered outside modal, portal to body    │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
User clicks attachment
        │
        ▼
AttachmentManager.onAttachmentClick(attachment, index)
        │
        ▼
Form.onAttachmentClick → Page.openPreview(index)
        │
        ▼
useAttachmentPreviewController
  ├─ Sets selectedIndex
  ├─ Loads preview blob via API
  └─ Returns floatingPreview or pinnedPreview
        │
        ▼
Rendered via {floatingPreview} or DraggableModal.rightPanel
```

## Key Patterns

### State Lifting
`pendingAttachmentIds` lives in Page, not Form. This survives modal layout changes (floating ↔ split-view) which can remount child components.

### Content-Based Guards
`onVisibleAttachmentsChange` only fires when attachment IDs actually change, not on every array reference change. Prevents infinite loops.

### Controlled/Uncontrolled Props
Forms accept optional `pendingAttachmentIds` prop. If provided, uses controlled mode. Otherwise, manages internal state.

### Single JSX Tree
DraggableModal renders one JSX tree for all layouts. Children stay mounted when switching between floating/split-view.

## Files

| Component | File | Responsibility |
|-----------|------|----------------|
| Page | `pages/Verifications.tsx` | State owner, orchestrates preview |
| Hook | `hooks/useAttachmentPreviewController.tsx` | Preview logic, blob loading |
| Modal | `components/DraggableModal.tsx` | Layout modes, drag/resize |
| Preview | `components/AttachmentPreviewPanel.tsx` | Preview UI, zoom/pan |
| Manager | `components/AttachmentManager.tsx` | Upload, list, select existing |
| Form | `components/forms/VerificationForm.tsx` | Form fields, passes callbacks |
