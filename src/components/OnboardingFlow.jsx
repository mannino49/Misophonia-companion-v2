import React, { useState } from 'react';
import '../App.css';

// Onboarding flow for sufferers (individuals with misophonia)
function OnboardingFlow({ onComplete }) {
  const [step, setStep] = useState(1);
  const [userProfile, setUserProfile] = useState({
    name: '',
    age: '',
    pronouns: '',
    country: '',
    triggers: [],
    symptomsBegin: '',
    frequency: '',
    intensity: 5,
    impacts: [],
    responses: [],
    copingMethods: '',
    goals: [],
    trackSymptoms: false,
    consentToDataUse: false,
    userType: 'sufferer'
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setUserProfile(prev => ({ ...prev, [name]: value }));
  };

  const handleCheckboxChange = (e) => {
    const { name, checked } = e.target;
    setUserProfile(prev => ({ ...prev, [name]: checked }));
  };

  const handleMultiSelect = (field, value) => {
    setUserProfile(prev => {
      const currentValues = prev[field] || [];
      if (currentValues.includes(value)) {
        return { ...prev, [field]: currentValues.filter(item => item !== value) };
      } else {
        return { ...prev, [field]: [...currentValues, value] };
      }
    });
  };

  const nextStep = () => {
    setStep(prev => prev + 1);
  };

  const prevStep = () => {
    setStep(prev => prev - 1);
  };

  const completeOnboarding = () => {
    // Save user profile to local storage or database
    localStorage.setItem('userProfile', JSON.stringify(userProfile));
    localStorage.setItem('onboardingComplete', 'true');
    onComplete(userProfile);
  };

  // Common triggers for misophonia
  const commonTriggers = [
    'Chewing sounds', 'Breathing sounds', 'Sniffling', 'Pen clicking', 
    'Keyboard typing', 'Throat clearing', 'Coughing', 'Snoring',
    'Whistling', 'Humming', 'Tapping', 'Cutlery on plates',
    'Plastic packaging', 'Slurping', 'Whispering', 'Certain voices'
  ];

  // Rendering different steps of the onboarding flow
  const renderStep = () => {
    switch(step) {
      case 1: // Welcome Screen
        return (
          <div className="onboarding-step welcome-step">
            <h1>Welcome to Misophonia Companion</h1>
            <p className="empathetic-message">You're not alone. We're here to support you.</p>
            <p>This companion app is designed to help you understand, manage, and track your misophonia experiences.</p>
            <button className="primary-button" onClick={nextStep}>Begin</button>
          </div>
        );
      
      case 2: // Basic Info
        return (
          <div className="onboarding-step">
            <h2>Tell us about yourself</h2>
            <p>This information helps us personalize your experience.</p>
            
            <div className="form-group">
              <label htmlFor="name">Name or pseudonym</label>
              <input 
                type="text" 
                id="name" 
                name="name" 
                value={userProfile.name} 
                onChange={handleInputChange} 
                placeholder="How would you like to be addressed?"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="age">Age</label>
              <input 
                type="number" 
                id="age" 
                name="age" 
                value={userProfile.age} 
                onChange={handleInputChange} 
                placeholder="Your age"
                min="1"
                max="120"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="pronouns">Pronouns</label>
              <select 
                id="pronouns" 
                name="pronouns" 
                value={userProfile.pronouns} 
                onChange={handleInputChange}
              >
                <option value="">Select your pronouns</option>
                <option value="he/him">He/Him</option>
                <option value="she/her">She/Her</option>
                <option value="they/them">They/Them</option>
                <option value="other">Other/Prefer not to say</option>
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="country">Country/Time Zone</label>
              <input 
                type="text" 
                id="country" 
                name="country" 
                value={userProfile.country} 
                onChange={handleInputChange} 
                placeholder="Your location"
              />
            </div>
            
            <div className="button-group">
              <button className="secondary-button" onClick={prevStep}>Back</button>
              <button className="primary-button" onClick={nextStep}>Continue</button>
            </div>
          </div>
        );
      
      case 3: // Symptom Assessment
        return (
          <div className="onboarding-step">
            <h2>Symptom Assessment</h2>
            <p>Understanding your triggers and reactions helps us provide better support.</p>
            
            <div className="form-group">
              <label>What sounds trigger you most?</label>
              <div className="checkbox-grid">
                {commonTriggers.map(trigger => (
                  <div key={trigger} className="checkbox-item">
                    <input 
                      type="checkbox" 
                      id={trigger.replace(/\s+/g, '-').toLowerCase()} 
                      checked={userProfile.triggers.includes(trigger)}
                      onChange={() => handleMultiSelect('triggers', trigger)}
                    />
                    <label htmlFor={trigger.replace(/\s+/g, '-').toLowerCase()}>{trigger}</label>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="form-group">
              <label htmlFor="symptomsBegin">When did your symptoms begin?</label>
              <select 
                id="symptomsBegin" 
                name="symptomsBegin" 
                value={userProfile.symptomsBegin} 
                onChange={handleInputChange}
              >
                <option value="">Select when symptoms began</option>
                <option value="childhood">Childhood (before 12)</option>
                <option value="adolescence">Adolescence (12-18)</option>
                <option value="young-adult">Young Adult (19-30)</option>
                <option value="adult">Adult (31+)</option>
                <option value="unsure">Unsure</option>
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="frequency">How often do you experience misophonic episodes?</label>
              <select 
                id="frequency" 
                name="frequency" 
                value={userProfile.frequency} 
                onChange={handleInputChange}
              >
                <option value="">Select frequency</option>
                <option value="rarely">Rarely (few times a month)</option>
                <option value="occasionally">Occasionally (few times a week)</option>
                <option value="frequently">Frequently (daily)</option>
                <option value="constantly">Constantly (multiple times daily)</option>
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="intensity">How intense is your reaction usually? (1-10)</label>
              <div className="slider-container">
                <input 
                  type="range" 
                  id="intensity" 
                  name="intensity" 
                  min="1" 
                  max="10" 
                  value={userProfile.intensity} 
                  onChange={handleInputChange}
                />
                <div className="slider-labels">
                  <span>1 😌</span>
                  <span>5 😟</span>
                  <span>10 😡</span>
                </div>
              </div>
            </div>
            
            <div className="button-group">
              <button className="secondary-button" onClick={prevStep}>Back</button>
              <button className="primary-button" onClick={nextStep}>Continue</button>
            </div>
          </div>
        );
      
      case 4: // Emotional & Functional Impact
        return (
          <div className="onboarding-step">
            <h2>Impact Assessment</h2>
            <p>Understanding how misophonia affects your life helps us provide relevant support.</p>
            
            <div className="form-group">
              <label>How does misophonia affect your daily life?</label>
              <div className="checkbox-grid">
                {['Work', 'School', 'Relationships', 'Sleep', 'Social activities', 'Eating', 'Travel', 'Mental health'].map(impact => (
                  <div key={impact} className="checkbox-item">
                    <input 
                      type="checkbox" 
                      id={impact.replace(/\s+/g, '-').toLowerCase()} 
                      checked={userProfile.impacts.includes(impact)}
                      onChange={() => handleMultiSelect('impacts', impact)}
                    />
                    <label htmlFor={impact.replace(/\s+/g, '-').toLowerCase()}>{impact}</label>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="form-group">
              <label>How do you usually respond when triggered?</label>
              <div className="checkbox-grid">
                {['Fight (anger/irritation)', 'Flight (leaving the situation)', 'Freeze (unable to move/speak)', 'Shutdown (emotional withdrawal)', 'Masking (hiding reactions)'].map(response => (
                  <div key={response} className="checkbox-item">
                    <input 
                      type="checkbox" 
                      id={response.replace(/[()\s+]/g, '-').toLowerCase()} 
                      checked={userProfile.responses.includes(response)}
                      onChange={() => handleMultiSelect('responses', response)}
                    />
                    <label htmlFor={response.replace(/[()\s+]/g, '-').toLowerCase()}>{response}</label>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="form-group">
              <label htmlFor="copingMethods">What have you tried to cope or treat it?</label>
              <textarea 
                id="copingMethods" 
                name="copingMethods" 
                value={userProfile.copingMethods} 
                onChange={handleInputChange} 
                placeholder="Share any strategies or treatments you've tried..."
                rows="4"
              />
            </div>
            
            <div className="button-group">
              <button className="secondary-button" onClick={prevStep}>Back</button>
              <button className="primary-button" onClick={nextStep}>Continue</button>
            </div>
          </div>
        );
      
      case 5: // Goals & Preferences
        return (
          <div className="onboarding-step">
            <h2>Goals & Preferences</h2>
            <p>Help us understand what you hope to achieve with this companion.</p>
            
            <div className="form-group">
              <label>What are you hoping to get from this companion?</label>
              <div className="checkbox-grid">
                {['Relief strategies', 'Better understanding', 'Self-tracking tools', 'New treatment options', 'Community connection', 'Research information'].map(goal => (
                  <div key={goal} className="checkbox-item">
                    <input 
                      type="checkbox" 
                      id={goal.replace(/\s+/g, '-').toLowerCase()} 
                      checked={userProfile.goals.includes(goal)}
                      onChange={() => handleMultiSelect('goals', goal)}
                    />
                    <label htmlFor={goal.replace(/\s+/g, '-').toLowerCase()}>{goal}</label>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="form-group">
              <div className="checkbox-item">
                <input 
                  type="checkbox" 
                  id="trackSymptoms" 
                  name="trackSymptoms" 
                  checked={userProfile.trackSymptoms}
                  onChange={handleCheckboxChange}
                />
                <label htmlFor="trackSymptoms">Would you like to track symptoms over time?</label>
              </div>
            </div>
            
            <div className="form-group">
              <div className="checkbox-item">
                <input 
                  type="checkbox" 
                  id="consentToDataUse" 
                  name="consentToDataUse" 
                  checked={userProfile.consentToDataUse}
                  onChange={handleCheckboxChange}
                />
                <label htmlFor="consentToDataUse">I consent to anonymous data use for future insights and research</label>
              </div>
              <p className="consent-note">Your data will never be shared with third parties and will only be used in anonymous, aggregated form to improve misophonia research and this application.</p>
            </div>
            
            <div className="button-group">
              <button className="secondary-button" onClick={prevStep}>Back</button>
              <button className="primary-button" onClick={nextStep}>Continue</button>
            </div>
          </div>
        );
      
      case 6: // Profile Creation + Dashboard Preview
        return (
          <div className="onboarding-step">
            <h2>Your Personalized Dashboard</h2>
            <p>Based on your answers, we've created a personalized experience for you.</p>
            
            <div className="dashboard-preview">
              <h3>Here's what you'll be able to do:</h3>
              
              <div className="feature-card">
                <div className="feature-icon">📝</div>
                <div className="feature-content">
                  <h4>Triggers Journal</h4>
                  <p>Track and analyze your trigger patterns over time.</p>
                </div>
              </div>
              
              <div className="feature-card">
                <div className="feature-icon">📊</div>
                <div className="feature-content">
                  <h4>Symptom Graph</h4>
                  <p>Visualize your misophonia intensity and frequency.</p>
                </div>
              </div>
              
              <div className="feature-card">
                <div className="feature-icon">🧘</div>
                <div className="feature-content">
                  <h4>Calming Strategies</h4>
                  <p>Access personalized coping techniques.</p>
                </div>
              </div>
              
              <div className="feature-card">
                <div className="feature-icon">🤖</div>
                <div className="feature-content">
                  <h4>AI Coach</h4>
                  <p>Get support and answers from our research-backed AI.</p>
                </div>
              </div>
            </div>
            
            <div className="button-group">
              <button className="secondary-button" onClick={prevStep}>Back</button>
              <button className="primary-button" onClick={completeOnboarding}>Start My Journey</button>
            </div>
          </div>
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="onboarding-container">
      <div className="progress-bar">
        <div 
          className="progress" 
          style={{ width: `${(step / 6) * 100}%` }}
        ></div>
      </div>
      {renderStep()}
    </div>
  );
}

export default OnboardingFlow;
