<!-- File: documents/development/habit-tracking-implementation-plan.md -->
################################################################################
# File: documents/development/habit-tracking-implementation-plan.md
################################################################################
# Habit Loop Tracking System: Implementation Plan

## Overview

This plan outlines the implementation of the Habit Loop tracking system for the Misophonia Companion app. The system follows the trigger awareness → emotional regulation → insight → progress → loop cycle to help users develop better coping mechanisms over time.

```
Trigger Log → Coping Tools → Pattern Recognition → Rewards → Insights
```

## Current Status (May 2025)

⏳ **Planning Phase:**
- Core concept defined
- User stories documented
- Technical architecture outlined

## Implementation Timeline

### 1. User Authentication & Profile System (Week 1)

- [ ] Set up Firebase Authentication
- [ ] Create user profile structure in Firestore
- [ ] Implement user onboarding flow
- [ ] Design and implement user preferences

### 2. Trigger Logging System (Week 1-2)

- [ ] Design trigger logging UI components:
  ```jsx
  // TriggerLogPrompt.jsx
  function TriggerLogPrompt() {
    return (
      <div className="trigger-prompt">
        <h3>Did you experience a sound trigger today?</h3>
        <div className="button-group">
          <Button onClick={() => openLogForm()} variant="primary">Yes</Button>
          <Button onClick={() => dismissPrompt()} variant="outline">Not today</Button>
        </div>
      </div>
    );
  }
  ```

- [ ] Implement quick log form:
  ```jsx
  // QuickLogForm.jsx
  function QuickLogForm() {
    const [sound, setSound] = useState('');
    const [location, setLocation] = useState('');
    const [intensity, setIntensity] = useState(5);
    const [copingStrategy, setCopingStrategy] = useState('');
    
    const handleSubmit = async (e) => {
      e.preventDefault();
      // Save to Firestore
      const triggerRef = collection(db, 'users', userId, 'triggers');
      await addDoc(triggerRef, {
        sound,
        location,
        intensity,
        copingStrategy,
        timestamp: serverTimestamp(),
      });
      
      // Show feedback and suggested tool
      showFeedback(intensity, sound, location);
    };
    
    return (
      <form onSubmit={handleSubmit} className="quick-log-form">
        <h3>Quick Trigger Log</h3>
        <p className="timer">30-second log</p>
        
        <div className="form-group">
          <label>What was the sound?</label>
          <select value={sound} onChange={(e) => setSound(e.target.value)}>
            <option value="">Select a sound</option>
            <option value="chewing">Chewing/Eating sounds</option>
            <option value="breathing">Breathing/Sniffing</option>
            <option value="tapping">Tapping/Clicking</option>
            <option value="keyboard">Keyboard/Typing</option>
            <option value="custom">Other (specify)</option>
          </select>
          {sound === 'custom' && (
            <input 
              type="text" 
              placeholder="Describe the sound" 
              onChange={(e) => setSound(e.target.value)} 
            />
          )}
        </div>
        
        <div className="form-group">
          <label>Where were you?</label>
          <select value={location} onChange={(e) => setLocation(e.target.value)}>
            <option value="">Select location</option>
            <option value="home">Home</option>
            <option value="work">Work</option>
            <option value="school">School</option>
            <option value="public">Public place</option>
            <option value="transit">Transit/Car</option>
            <option value="custom">Other (specify)</option>
          </select>
          {location === 'custom' && (
            <input 
              type="text" 
              placeholder="Describe the location" 
              onChange={(e) => setLocation(e.target.value)} 
            />
          )}
        </div>
        
        <div className="form-group">
          <label>How strong was your reaction? ({intensity})</label>
          <input 
            type="range" 
            min="1" 
            max="10" 
            value={intensity} 
            onChange={(e) => setIntensity(parseInt(e.target.value))} 
          />
          <div className="range-labels">
            <span>Mild</span>
            <span>Moderate</span>
            <span>Severe</span>
          </div>
        </div>
        
        <div className="form-group">
          <label>What did you do afterward?</label>
          <select value={copingStrategy} onChange={(e) => setCopingStrategy(e.target.value)}>
            <option value="">Select response</option>
            <option value="left">Left the situation</option>
            <option value="headphones">Used headphones/earplugs</option>
            <option value="asked">Asked person to stop</option>
            <option value="breathed">Deep breathing</option>
            <option value="distracted">Distracted myself</option>
            <option value="custom">Other (specify)</option>
          </select>
          {copingStrategy === 'custom' && (
            <input 
              type="text" 
              placeholder="Describe what you did" 
              onChange={(e) => setCopingStrategy(e.target.value)} 
            />
          )}
        </div>
        
        <button type="submit" className="submit-button">Log Trigger</button>
      </form>
    );
  }
  ```

- [ ] Create Firestore database structure for trigger logs
- [ ] Implement trigger log submission and storage

### 3. Coping Tools Library (Week 2-3)

- [ ] Implement feedback system after logging:
  ```jsx
  // FeedbackComponent.jsx
  function FeedbackComponent({ intensity, sound, location }) {
    const [tool, setTool] = useState(null);
    
    useEffect(() => {
      // Select appropriate tool based on intensity and context
      const suggestedTool = getSuggestedTool(intensity, sound, location);
      setTool(suggestedTool);
      
      // Update streak/score
      updateStreakAndScore();
    }, [intensity, sound, location]);
    
    return (
      <div className="feedback-container">
        <div className="feedback-message">
          <h3>Trigger Logged</h3>
          <p>You logged a {intensity}-level reaction to {sound} sounds at {location}.</p>
        </div>
        
        {tool && (
          <div className="suggested-tool">
            <h4>Try this {tool.duration}-second reset:</h4>
            <div className="tool-card">
              <img src={tool.icon} alt={tool.name} />
              <h5>{tool.name}</h5>
              <p>{tool.description}</p>
              <button onClick={() => startTool(tool)}>Start</button>
            </div>
          </div>
        )}
        
        <div className="streak-update">
          <p>Current streak: {streak} days</p>
          <p>Calm score: {calmScore}</p>
        </div>
      </div>
    );
  }
  ```

- [ ] Create guided breathing exercise component
- [ ] Implement cognitive reframing tool
- [ ] Develop noise-masking audio player
- [ ] Design tool selection algorithm based on trigger context

### 4. Progress Tracking & Rewards (Week 3-4)

- [ ] Implement streak tracking system
- [ ] Create "calm score" mechanism
- [ ] Design and implement badges/achievements
- [ ] Build progress visualization components:
  ```jsx
  // ProgressDashboard.jsx
  function ProgressDashboard() {
    const [triggers, setTriggers] = useState([]);
    const [timeframe, setTimeframe] = useState('week');
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
      // Fetch trigger data based on timeframe
      fetchTriggerData(timeframe).then(data => {
        setTriggers(data);
        setLoading(false);
      });
    }, [timeframe]);
    
    return (
      <div className="progress-dashboard">
        <h2>Your Progress</h2>
        
        <div className="timeframe-selector">
          <button 
            className={timeframe === 'week' ? 'active' : ''}
            onClick={() => setTimeframe('week')}
          >
            Week
          </button>
          <button 
            className={timeframe === 'month' ? 'active' : ''}
            onClick={() => setTimeframe('month')}
          >
            Month
          </button>
          <button 
            className={timeframe === 'year' ? 'active' : ''}
            onClick={() => setTimeframe('year')}
          >
            Year
          </button>
        </div>
        
        {loading ? (
          <p>Loading your data...</p>
        ) : (
          <>
            <div className="stats-overview">
              <div className="stat-card">
                <h3>Triggers Logged</h3>
                <p className="stat-value">{triggers.length}</p>
              </div>
              <div className="stat-card">
                <h3>Average Intensity</h3>
                <p className="stat-value">
                  {calculateAverageIntensity(triggers).toFixed(1)}
                </p>
              </div>
              <div className="stat-card">
                <h3>Most Common Trigger</h3>
                <p className="stat-value">{findMostCommonTrigger(triggers)}</p>
              </div>
            </div>
            
            <div className="charts-container">
              <div className="chart">
                <h3>Intensity Over Time</h3>
                <IntensityLineChart data={triggers} />
              </div>
              <div className="chart">
                <h3>Trigger Distribution</h3>
                <TriggerPieChart data={triggers} />
              </div>
            </div>
            
            <div className="achievements">
              <h3>Your Achievements</h3>
              <div className="badges-container">
                {userBadges.map(badge => (
                  <Badge key={badge.id} badge={badge} />
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    );
  }
  ```

### 5. Pattern Recognition & Insights (Week 4-5)

- [ ] Implement data analysis algorithms
- [ ] Create insight generation system:
  ```javascript
  // insights.js
  function generateInsights(triggerData) {
    const insights = [];
    
    // Time-based patterns
    const timePatterns = analyzeTimePatterns(triggerData);
    if (timePatterns.hasPeakTime) {
      insights.push({
        type: 'time_pattern',
        title: `Peak Trigger Time: ${timePatterns.peakHour}`,
        description: `You tend to get triggered around ${formatHour(timePatterns.peakHour)}. ` +
                    `Try a preemptive reset at ${formatHour(timePatterns.peakHour - 1)}.`,
        actionable: true,
        action: {
          type: 'schedule_reminder',
          time: timePatterns.peakHour - 1,
          message: 'Preemptive reset reminder'
        }
      });
    }
    
    // Location patterns
    const locationPatterns = analyzeLocationPatterns(triggerData);
    if (locationPatterns.mostTriggeringLocation) {
      insights.push({
        type: 'location_pattern',
        title: `Triggering Location: ${locationPatterns.mostTriggeringLocation}`,
        description: `${locationPatterns.mostTriggeringLocation} seems to be a challenging environment for you. ` +
                    `Consider preparing with noise-cancelling headphones or having a conversation with others there.`,
        actionable: true,
        action: {
          type: 'show_article',
          articleId: 'preparing-for-triggering-environments'
        }
      });
    }
    
    // Improvement insights
    const progressInsights = analyzeProgress(triggerData);
    if (progressInsights.intensityDecreasing) {
      insights.push({
        type: 'progress',
        title: 'Your Reaction Intensity Is Decreasing',
        description: `Great job! Your average reaction intensity has decreased by ` +
                    `${progressInsights.intensityChangePercent}% over the last month.`,
        actionable: false
      });
    }
    
    // Coping strategy effectiveness
    const copingInsights = analyzeCopingStrategies(triggerData);
    if (copingInsights.mostEffectiveStrategy) {
      insights.push({
        type: 'coping_strategy',
        title: `Effective Strategy: ${copingInsights.mostEffectiveStrategy}`,
        description: `${copingInsights.mostEffectiveStrategy} seems to work well for you. ` +
                    `Consider using this strategy more often when triggered.`,
        actionable: true,
        action: {
          type: 'favorite_strategy',
          strategyId: copingInsights.mostEffectiveStrategyId
        }
      });
    }
    
    return insights;
  }
  ```

- [ ] Design insight notification system
- [ ] Implement personalized recommendations

### 6. Integration with Research Vector Database (Week 5-6)

- [ ] Connect habit tracking system with existing RAG interface
- [ ] Implement research-backed recommendations based on trigger patterns
- [ ] Create educational content delivery based on user needs

### 7. Testing & Optimization (Week 6-7)

- [ ] Conduct usability testing with sample users
- [ ] Optimize UI/UX for quick logging (target: under 30 seconds)
- [ ] Test notification timing and frequency
- [ ] Optimize data analysis algorithms

### 8. Deployment & Monitoring (Week 7-8)

- [ ] Deploy to staging environment
- [ ] Conduct beta testing with limited users
- [ ] Set up analytics to track feature usage
- [ ] Gradual rollout to production

## Technical Architecture

### Components

1. **User Profile System**
   - Firebase Authentication for user management
   - Firestore for user preferences and settings

2. **Trigger Logging System**
   - React components for quick logging interface
   - Firestore for trigger data storage
   - Cloud Functions for data processing

3. **Coping Tools Library**
   - Audio files stored in Firebase Storage
   - React components for tool interfaces
   - Tool recommendation algorithm

4. **Progress Tracking**
   - Streak and score calculation in Cloud Functions
   - Chart.js or D3.js for data visualization
   - Badge/achievement system

5. **Pattern Recognition**
   - Data analysis algorithms in Cloud Functions
   - Scheduled insight generation
   - Notification system using Firebase Cloud Messaging

6. **Research Integration**
   - Connection to existing vector database
   - Personalized content delivery

## Data Flow

1. **Trigger Logging**
   ```
   User Input → React Form → Firestore → Cloud Function (for processing)
   ```

2. **Coping Tool Recommendation**
   ```
   Trigger Data → Recommendation Algorithm → Tool Selection → User Interface
   ```

3. **Insight Generation**
   ```
   Trigger Data → Analysis Algorithms → Insight Generation → Notification
   ```

4. **Progress Tracking**
   ```
   Trigger Data → Statistical Analysis → Visualization → User Dashboard
   ```

## Next Steps

1. Finalize UI/UX designs for the trigger logging flow
2. Set up Firebase Authentication and user profile structure
3. Implement the core trigger logging functionality
4. Begin development of the coping tools library

## References

- [Product Vision](./product-vision.md)
- [Feature Roadmap](./feature-roadmap.md)
- [User Stories](./user-stories.md)
- [Technical Architecture](./technical-architecture.md)
- [Vector Database Implementation](./misophonia-vector-db-implementation-plan.md)
