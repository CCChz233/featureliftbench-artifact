;; Capture module-level __all__ assignments for EXPORTS edges.
(assignment
  left: (identifier) @exports.name
  right: (_) @exports.value)
