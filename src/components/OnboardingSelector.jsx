import React, { useState } from 'react';
import '../App.css';
import OnboardingFlow from './OnboardingFlow';
import ParentOnboarding from './ParentOnboarding';
import ClinicianOnboarding from './ClinicianOnboarding';

function OnboardingSelector({ onComplete }) {
  const [userType, setUserType] = useState(null);

  const handleUserTypeSelect = (type) => {
    setUserType(type);
  };

  const handleOnboardingComplete = (profile) => {
    // Pass the completed profile back to the parent component
    onComplete(profile);
  };

  // If user type is selected, show the appropriate onboarding flow
  if (userType === 'sufferer') {
    return <OnboardingFlow onComplete={handleOnboardingComplete} />;
  } else if (userType === 'parent') {
    return <ParentOnboarding onComplete={handleOnboardingComplete} />;
  } else if (userType === 'clinician') {
    return <ClinicianOnboarding onComplete={handleOnboardingComplete} />;
  }

  // Otherwise, show the user type selection screen
  return (
    <div className="onboarding-container">
      <div className="onboarding-step welcome-step">
        <h1>Welcome to Misophonia Companion</h1>
        <p className="subtitle">A supportive space for everyone affected by misophonia</p>
        
        <h2>I am a...</h2>
        <div className="user-type-selection">
          <div 
            className="user-type-card" 
            onClick={() => handleUserTypeSelect('sufferer')}
          >
            <div className="user-type-icon">😌</div>
            <h3>Person with Misophonia</h3>
            <p>Get personalized support, tracking tools, and coping strategies</p>
          </div>
          
          <div 
            className="user-type-card" 
            onClick={() => handleUserTypeSelect('parent')}
          >
            <div className="user-type-icon">👪</div>
            <h3>Parent or Caregiver</h3>
            <p>Find resources to help your child manage misophonia symptoms</p>
          </div>
          
          <div 
            className="user-type-card" 
            onClick={() => handleUserTypeSelect('clinician')}
          >
            <div className="user-type-icon">🩺</div>
            <h3>Healthcare Provider</h3>
            <p>Access evidence-based research and clinical resources</p>
          </div>
        </div>
        
        <p className="note">Your experience will be customized based on your selection</p>
      </div>
    </div>
  );
}

export default OnboardingSelector;
