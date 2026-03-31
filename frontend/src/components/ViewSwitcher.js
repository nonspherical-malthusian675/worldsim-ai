import React from 'react';

const ViewSwitcher = ({ activeView, onViewChange }) => (
  <div className="view-switcher">
    <button
      className={`view-tab ${activeView === '2d' ? 'active' : ''}`}
      onClick={() => onViewChange('2d')}
    >
      📊 2D Grid
    </button>
    <button
      className={`view-tab ${activeView === '3d' ? 'active' : ''}`}
      onClick={() => onViewChange('3d')}
    >
      🌍 3D World
    </button>
  </div>
);

export default ViewSwitcher;
