import React from 'react';

export const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  loading = false,
  icon,
  ...props
}) => {
  const variants = {
    primary: 'btn-primary',
    danger: 'btn-danger',
    ghost: 'btn-ghost',
    secondary: 'btn-secondary',
  };

  return (
    <button
      className={`btn btn-${size} ${variants[variant] || variants.primary} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <span className="button-spinner" aria-hidden="true" />}
      {!loading && icon && <span className="button-icon" aria-hidden="true">{icon}</span>}
      {children}
    </button>
  );
};

export const Card = ({ children, title, eyebrow, action, className = '', ...props }) => (
  <section className={`card ${className}`} {...props}>
    {(title || eyebrow || action) && (
      <div className="card-header">
        <div>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          {title && <span className="card-title">{title}</span>}
        </div>
        {action}
      </div>
    )}
    {children}
  </section>
);

export const StatCard = ({ label, value, detail, trend, accent = 'green', className = '' }) => (
  <div className={`stat-card stat-card-${accent} ${className}`}>
    <div className="stat-label">{label}</div>
    <div className="stat-value">{value}</div>
    <div className="stat-meta">
      {trend && <span className={trend.startsWith('-') ? 'text-red' : 'text-green'}>{trend}</span>}
      {detail}
    </div>
  </div>
);

export const Badge = ({ children, variant = 'pending', dot = false, className = '' }) => (
  <span className={`badge ${variant} ${className}`}>
    {dot && <span className="badge-dot" aria-hidden="true" />}
    {children}
  </span>
);

export const Input = ({ label, hint, error, className = '', ...props }) => (
  <div className={`form-group ${className}`}>
    {label && <label className="form-label" htmlFor={props.id}>{label}</label>}
    <input className={`form-input ${error ? 'input-error' : ''}`} {...props} />
    {error ? <span className="form-error">{error}</span> : hint && <span className="form-hint">{hint}</span>}
  </div>
);

export const Select = ({ label, children, className = '', ...props }) => (
  <div className={`form-group ${className}`}>
    {label && <label className="form-label" htmlFor={props.id}>{label}</label>}
    <select className="form-input" {...props}>{children}</select>
  </div>
);

export const Table = ({ headers, children, caption, className = '' }) => (
  <div className={`trade-table-container ${className}`}>
    {caption && <div className="table-caption">{caption}</div>}
    <table className="trade-table">
      <thead><tr>{headers.map((header, index) => <th key={`${header}-${index}`}>{header}</th>)}</tr></thead>
      <tbody>{children}</tbody>
    </table>
  </div>
);

export const EmptyState = ({ icon = '◌', title, description, action }) => (
  <div className="empty-state">
    <div className="empty-state-icon" aria-hidden="true">{icon}</div>
    <h3>{title}</h3>
    {description && <p>{description}</p>}
    {action}
  </div>
);

export const PageIntro = ({ eyebrow, title, description, actions }) => (
  <div className="page-intro">
    <div>
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </div>
    {actions && <div className="page-intro-actions">{actions}</div>}
  </div>
);

export const ProgressBar = ({ value = 0, label, tone = 'green' }) => (
  <div className="progress-wrap">
    {(label || value !== undefined) && (
      <div className="progress-label"><span>{label}</span><span>{Math.round(value)}%</span></div>
    )}
    <div className="progress-track"><div className={`progress-fill progress-${tone}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} /></div>
  </div>
);
