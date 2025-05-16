import React, { useState } from 'react';
import '../App.css';

// Onboarding flow for clinicians working with misophonia patients
function ClinicianOnboarding({ onComplete }) {
  const [step, setStep] = useState(1);
  const [userProfile, setUserProfile] = useState({
    name: '',
    credentials: '',
    specialty: '',
    practiceType: '',
    yearsExperience: '',
    misophoniaExperience: '',
    country: '',
    patientAgeGroups: [],
    treatmentApproaches: [],
    researchInterests: [],
    goals: [],
    consentToDataUse: false,
    userType: 'clinician'
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

  // Rendering different steps of the onboarding flow
  const renderStep = () => {
    switch(step) {
      case 1: // Welcome Screen
        return (
          <div className="onboarding-step welcome-step">
            <h1>Welcome to Misophonia Companion</h1>
            <p className="empathetic-message">A research-backed resource for clinicians working with misophonia patients.</p>
            <p>This companion app provides evidence-based information and clinical tools to support your practice.</p>
            <button className="primary-button" onClick={nextStep}>Begin</button>
          </div>
        );
      
      case 2: // Professional Info
        return (
          <div className="onboarding-step">
            <h2>Professional Information</h2>
            <p>Help us customize your experience based on your clinical background.</p>
            
            <div className="form-group">
              <label htmlFor="name">Name</label>
              <input 
                type="text" 
                id="name" 
                name="name" 
                value={userProfile.name} 
                onChange={handleInputChange} 
                placeholder="Your name"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="credentials">Credentials</label>
              <input 
                type="text" 
                id="credentials" 
                name="credentials" 
                value={userProfile.credentials} 
                onChange={handleInputChange} 
                placeholder="MD, PhD, PsyD, LCSW, etc."
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="specialty">Primary Specialty</label>
              <select 
                id="specialty" 
                name="specialty" 
                value={userProfile.specialty} 
                onChange={handleInputChange}
              >
                <option value="">Select specialty</option>
                <option value="psychiatry">Psychiatry</option>
                <option value="psychology">Psychology</option>
                <option value="neurology">Neurology</option>
                <option value="audiology">Audiology</option>
                <option value="social-work">Social Work</option>
                <option value="occupational-therapy">Occupational Therapy</option>
                <option value="speech-language">Speech-Language Pathology</option>
                <option value="other">Other</option>
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="practiceType">Practice Setting</label>
              <select 
                id="practiceType" 
                name="practiceType" 
                value={userProfile.practiceType} 
                onChange={handleInputChange}
              >
                <option value="">Select practice setting</option>
                <option value="private">Private Practice</option>
                <option value="hospital">Hospital</option>
                <option value="academic">Academic/Research</option>
                <option value="community">Community Mental Health</option>
                <option value="school">School/University</option>
                <option value="other">Other</option>
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="yearsExperience">Years in Practice</label>
              <select 
                id="yearsExperience" 
                name="yearsExperience" 
                value={userProfile.yearsExperience} 
                onChange={handleInputChange}
              >
                <option value="">Select experience</option>
                <option value="0-2">0-2 years</option>
                <option value="3-5">3-5 years</option>
                <option value="6-10">6-10 years</option>
                <option value="11-20">11-20 years</option>
                <option value="20+">20+ years</option>
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="country">Country/Region</label>
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
      
      case 3: // Misophonia Experience
        return (
          <div className="onboarding-step">
            <h2>Misophonia Experience</h2>
            <p>Tell us about your experience with misophonia patients.</p>
            
            <div className="form-group">
              <label htmlFor="misophoniaExperience">Experience with Misophonia</label>
              <select 
                id="misophoniaExperience" 
                name="misophoniaExperience" 
                value={userProfile.misophoniaExperience} 
                onChange={handleInputChange}
              >
                <option value="">Select experience level</option>
                <option value="none">No experience yet</option>
                <option value="limited">Limited (1-5 patients)</option>
                <option value="moderate">Moderate (6-20 patients)</option>
                <option value="extensive">Extensive (20+ patients)</option>
                <option value="specialist">Specialist in misophonia</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Patient Age Groups (select all that apply)</label>
              <div className="checkbox-grid">
                {['Children (under 12)', 'Adolescents (12-17)', 'Young Adults (18-25)', 'Adults (26-64)', 'Older Adults (65+)'].map(group => (
                  <div key={group} className="checkbox-item">
                    <input 
                      type="checkbox" 
                      id={group.replace(/[()\s+]/g, '-').toLowerCase()} 
                      checked={userProfile.patientAgeGroups.includes(group)}
                      onChange={() => handleMultiSelect('patientAgeGroups', group)}
                    />
                    <label htmlFor={group.replace(/[()\s+]/g, '-').toLowerCase()}>{group}</label>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="form-group">
              <label>Treatment Approaches (select all that apply)</label>
              <div className="checkbox-grid">
                {['Cognitive Behavioral Therapy', 'Exposure Therapy', 'Mindfulness', 'Sound Therapy', 'Medication Management', 'Family Therapy', 'Acceptance and Commitment Therapy', 'Other'].map(approach => (
                  <div key={approach} className="checkbox-item">
                    <input 
                      type="checkbox" 
                      id={approach.replace(/\s+/g, '-').toLowerCase()} 
                      checked={userProfile.treatmentApproaches.includes(approach)}
                      onChange={() => handleMultiSelect('treatmentApproaches', approach)}
                    />
                    <label htmlFor={approach.replace(/\s+/g, '-').toLowerCase()}>{approach}</label>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="button-group">
              <button className="secondary-button" onClick={prevStep}>Back</button>
              <button className="primary-button" onClick={nextStep}>Continue</button>
            </div>
          </div>
        );
      
      case 4: // Research Interests & Goals
        return (
          <div className="onboarding-step">
            <h2>Research Interests & Goals</h2>
            <p>Help us understand your clinical interests and what you hope to gain from this resource.</p>
            
            <div className="form-group">
              <label>Research Interests (select all that apply)</label>
              <div className="checkbox-grid">
                {['Neurological mechanisms', 'Treatment efficacy', 'Comorbidities', 'Developmental aspects', 'Assessment tools', 'Family dynamics', 'Educational accommodations', 'Other'].map(interest => (
                  <div key={interest} className="checkbox-item">
                    <input 
                      type="checkbox" 
                      id={interest.replace(/\s+/g, '-').toLowerCase()} 
                      checked={userProfile.researchInterests.includes(interest)}
                      onChange={() => handleMultiSelect('researchInterests', interest)}
                    />
                    <label htmlFor={interest.replace(/\s+/g, '-').toLowerCase()}>{interest}</label>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="form-group">
              <label>What are you hoping to gain from this companion? (select all that apply)</label>
              <div className="checkbox-grid">
                {['Treatment resources', 'Research updates', 'Assessment tools', 'Patient education materials', 'Colleague networking', 'Case consultation'].map(goal => (
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
                  id="consentToDataUse" 
                  name="consentToDataUse" 
                  checked={userProfile.consentToDataUse}
                  onChange={handleCheckboxChange}
                />
                <label htmlFor="consentToDataUse">I consent to anonymous data use for research purposes</label>
              </div>
              <p className="consent-note">Your data will never be shared with third parties and will only be used in anonymous, aggregated form to improve misophonia research and this application.</p>
            </div>
            
            <div className="button-group">
              <button className="secondary-button" onClick={prevStep}>Back</button>
              <button className="primary-button" onClick={nextStep}>Continue</button>
            </div>
          </div>
        );
      
      case 5: // Dashboard Preview
        return (
          <div className="onboarding-step">
            <h2>Your Clinical Dashboard</h2>
            <p>Based on your profile, we've customized your experience.</p>
            
            <div className="dashboard-preview">
              <h3>Here's what you'll have access to:</h3>
              
              <div className="feature-card">
                <div className="feature-icon">🔬</div>
                <div className="feature-content">
                  <h4>Research Library</h4>
                  <p>Access to our comprehensive database of 134+ misophonia research papers.</p>
                </div>
              </div>
              
              <div className="feature-card">
                <div className="feature-icon">📋</div>
                <div className="feature-content">
                  <h4>Assessment Tools</h4>
                  <p>Validated scales and questionnaires for clinical use.</p>
                </div>
              </div>
              
              <div className="feature-card">
                <div className="feature-icon">🧠</div>
                <div className="feature-content">
                  <h4>Treatment Protocols</h4>
                  <p>Evidence-based intervention strategies and resources.</p>
                </div>
              </div>
              
              <div className="feature-card">
                <div className="feature-icon">🤖</div>
                <div className="feature-content">
                  <h4>AI Research Assistant</h4>
                  <p>Query our research database with natural language questions.</p>
                </div>
              </div>
            </div>
            
            <div className="button-group">
              <button className="secondary-button" onClick={prevStep}>Back</button>
              <button className="primary-button" onClick={completeOnboarding}>Access Clinical Portal</button>
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
          style={{ width: `${(step / 5) * 100}%` }}
        ></div>
      </div>
      {renderStep()}
    </div>
  );
}

export default ClinicianOnboarding;
