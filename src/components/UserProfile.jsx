import React, { useState, useEffect } from 'react';
import '../App.css';
import '../onboarding.css';

function UserProfile({ userProfile, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [profile, setProfile] = useState(userProfile || {});

  useEffect(() => {
    if (userProfile) {
      setProfile(userProfile);
    }
  }, [userProfile]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setProfile(prev => ({ ...prev, [name]: value }));
  };

  const handleCheckboxChange = (e) => {
    const { name, checked } = e.target;
    setProfile(prev => ({ ...prev, [name]: checked }));
  };

  const handleMultiSelect = (field, value) => {
    setProfile(prev => {
      const currentValues = prev[field] || [];
      if (currentValues.includes(value)) {
        return { ...prev, [field]: currentValues.filter(item => item !== value) };
      } else {
        return { ...prev, [field]: [...currentValues, value] };
      }
    });
  };

  const saveProfile = () => {
    localStorage.setItem('userProfile', JSON.stringify(profile));
    onUpdate(profile);
    setEditing(false);
  };

  // Render different profile views based on user type
  const renderProfileView = () => {
    if (!profile) return null;

    if (profile.userType === 'sufferer') {
      return (
        <div className="profile-details">
          <h3>Your Profile</h3>
          <div className="profile-section">
            <h4>Personal Information</h4>
            <p><strong>Name:</strong> {profile.name || 'Not provided'}</p>
            <p><strong>Age:</strong> {profile.age || 'Not provided'}</p>
            <p><strong>Pronouns:</strong> {profile.pronouns || 'Not provided'}</p>
            <p><strong>Location:</strong> {profile.country || 'Not provided'}</p>
          </div>
          
          <div className="profile-section">
            <h4>Misophonia Details</h4>
            <p><strong>Common Triggers:</strong> {profile.triggers?.join(', ') || 'None specified'}</p>
            <p><strong>Symptoms Began:</strong> {profile.symptomsBegin || 'Not specified'}</p>
            <p><strong>Frequency:</strong> {profile.frequency || 'Not specified'}</p>
            <p><strong>Typical Intensity:</strong> {profile.intensity || 'Not specified'}/10</p>
          </div>
          
          <div className="profile-section">
            <h4>Impact & Responses</h4>
            <p><strong>Life Areas Affected:</strong> {profile.impacts?.join(', ') || 'None specified'}</p>
            <p><strong>Typical Responses:</strong> {profile.responses?.join(', ') || 'None specified'}</p>
          </div>
          
          <div className="profile-section">
            <h4>Goals & Preferences</h4>
            <p><strong>Goals:</strong> {profile.goals?.join(', ') || 'None specified'}</p>
            <p><strong>Track Symptoms:</strong> {profile.trackSymptoms ? 'Yes' : 'No'}</p>
          </div>
        </div>
      );
    } else if (profile.userType === 'parent') {
      return (
        <div className="profile-details">
          <h3>Your Profile</h3>
          <div className="profile-section">
            <h4>Personal Information</h4>
            <p><strong>Name:</strong> {profile.name || 'Not provided'}</p>
            <p><strong>Relationship:</strong> {profile.relationship || 'Not provided'}</p>
            <p><strong>Location:</strong> {profile.country || 'Not provided'}</p>
          </div>
          
          <div className="profile-section">
            <h4>Child's Information</h4>
            <p><strong>Age:</strong> {profile.childAge || 'Not provided'}</p>
            <p><strong>Pronouns:</strong> {profile.childPronouns || 'Not provided'}</p>
            <p><strong>Common Triggers:</strong> {profile.childTriggers?.join(', ') || 'None specified'}</p>
            <p><strong>Symptoms Began:</strong> {profile.symptomsBegin || 'Not specified'}</p>
            <p><strong>Frequency:</strong> {profile.frequency || 'Not specified'}</p>
            <p><strong>Typical Intensity:</strong> {profile.intensity || 'Not specified'}/10</p>
          </div>
          
          <div className="profile-section">
            <h4>Impact & Responses</h4>
            <p><strong>Life Areas Affected:</strong> {profile.impacts?.join(', ') || 'None specified'}</p>
            <p><strong>Typical Responses:</strong> {profile.responses?.join(', ') || 'None specified'}</p>
          </div>
          
          <div className="profile-section">
            <h4>Goals & Preferences</h4>
            <p><strong>Goals:</strong> {profile.goals?.join(', ') || 'None specified'}</p>
            <p><strong>Track Symptoms:</strong> {profile.trackSymptoms ? 'Yes' : 'No'}</p>
          </div>
        </div>
      );
    } else if (profile.userType === 'clinician') {
      return (
        <div className="profile-details">
          <h3>Your Professional Profile</h3>
          <div className="profile-section">
            <h4>Professional Information</h4>
            <p><strong>Name:</strong> {profile.name || 'Not provided'}</p>
            <p><strong>Credentials:</strong> {profile.credentials || 'Not provided'}</p>
            <p><strong>Specialty:</strong> {profile.specialty || 'Not provided'}</p>
            <p><strong>Practice Setting:</strong> {profile.practiceType || 'Not provided'}</p>
            <p><strong>Years Experience:</strong> {profile.yearsExperience || 'Not provided'}</p>
            <p><strong>Location:</strong> {profile.country || 'Not provided'}</p>
          </div>
          
          <div className="profile-section">
            <h4>Misophonia Experience</h4>
            <p><strong>Experience Level:</strong> {profile.misophoniaExperience || 'Not specified'}</p>
            <p><strong>Patient Age Groups:</strong> {profile.patientAgeGroups?.join(', ') || 'None specified'}</p>
            <p><strong>Treatment Approaches:</strong> {profile.treatmentApproaches?.join(', ') || 'None specified'}</p>
          </div>
          
          <div className="profile-section">
            <h4>Research & Goals</h4>
            <p><strong>Research Interests:</strong> {profile.researchInterests?.join(', ') || 'None specified'}</p>
            <p><strong>Goals:</strong> {profile.goals?.join(', ') || 'None specified'}</p>
          </div>
        </div>
      );
    }
    
    return null;
  };

  return (
    <div className="user-profile-container">
      {!editing ? (
        <>
          {renderProfileView()}
          <div className="profile-actions">
            <button className="secondary-button" onClick={() => setEditing(true)}>Edit Profile</button>
          </div>
        </>
      ) : (
        <div className="profile-edit-form">
          <h3>Edit Your Profile</h3>
          <p>Update your information below</p>
          
          {/* Basic info fields - common to all user types */}
          <div className="form-group">
            <label htmlFor="name">Name</label>
            <input 
              type="text" 
              id="name" 
              name="name" 
              value={profile.name || ''} 
              onChange={handleInputChange} 
              placeholder="Your name"
            />
          </div>
          
          {profile.userType === 'sufferer' && (
            <>
              <div className="form-group">
                <label htmlFor="age">Age</label>
                <input 
                  type="number" 
                  id="age" 
                  name="age" 
                  value={profile.age || ''} 
                  onChange={handleInputChange} 
                  placeholder="Your age"
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="pronouns">Pronouns</label>
                <select 
                  id="pronouns" 
                  name="pronouns" 
                  value={profile.pronouns || ''} 
                  onChange={handleInputChange}
                >
                  <option value="">Select your pronouns</option>
                  <option value="he/him">He/Him</option>
                  <option value="she/her">She/Her</option>
                  <option value="they/them">They/Them</option>
                  <option value="other">Other/Prefer not to say</option>
                </select>
              </div>
            </>
          )}
          
          {/* More fields would be added here based on user type */}
          
          <div className="form-group">
            <label htmlFor="country">Country/Location</label>
            <input 
              type="text" 
              id="country" 
              name="country" 
              value={profile.country || ''} 
              onChange={handleInputChange} 
              placeholder="Your location"
            />
          </div>
          
          <div className="profile-actions">
            <button className="secondary-button" onClick={() => setEditing(false)}>Cancel</button>
            <button className="primary-button" onClick={saveProfile}>Save Changes</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserProfile;
