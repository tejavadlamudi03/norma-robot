import React from 'react';
import { Outlet } from 'react-router-dom';
import Navigation from './Navigation';

const MainLayout: React.FC = () => {
  return (
    <div className="w-full min-h-screen flex flex-col bg-surface-base text-text-primary">
      <Navigation />
      <Outlet />
    </div>
  );
};

export default MainLayout;
