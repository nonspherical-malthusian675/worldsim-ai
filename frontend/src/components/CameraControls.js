import React from 'react';

const CameraControls = ({ onPreset, onZoomChange, onTimeOfDayChange, timeOfDay }) => (
  <div className="camera-controls">
    <div className="control-group">
      <label className="control-label">📷 View</label>
      <div className="btn-row">
        {['Top Down', 'Isometric', 'Free'].map((v) => (
          <button key={v} className="ctrl-btn small" onClick={() => onPreset(v.toLowerCase().replace(' ', '_'))}>
            {v}
          </button>
        ))}
      </div>
    </div>
    <div className="control-group">
      <label className="control-label">🌅 Lighting</label>
      <div className="btn-row">
        {['day', 'night'].map((v) => (
          <button key={v} className={`ctrl-btn small ${timeOfDay === v ? 'active' : ''}`}
                  onClick={() => onTimeOfDayChange(v)}>
            {v === 'day' ? '☀️' : '🌙'} {v}
          </button>
        ))}
      </div>
    </div>
  </div>
);

export default CameraControls;
