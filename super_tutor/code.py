graph TD
    Start([Start 2‑Hour Session]) --> SetGoals[Set learning objectives & agenda]
    SetGoals --> AssessPrior[Assess prior knowledge]
    
    %% === 1. SPACED REPETITION (Micro-spacing) ===
    AssessPrior --> PriorGaps{Significant gaps?}
    PriorGaps -->|Yes| Bridge[Quick review or bridging concept]
    Bridge --> SpacedInit[<b>Spaced Repetition Trigger</b><br/>Note: This topic needs revisiting later]
    SpacedInit --> NextTopic
    
    PriorGaps -->|No| NextTopic[Introduce next topic]

    NextTopic --> Present[Explain concept with examples]
    
    %% === 2. ACTIVE RECALL ===
    Present --> ActiveRecall[<b>Active Recall Prompt</b><br/>Ask student to explain/recall without notes]
    ActiveRecall --> CheckUnderstand{Check understanding:<br/>problem or open-ended question}
    
    CheckUnderstand -->|Correct / confident| Reinforce[Reinforce with positive feedback]
    Reinforce --> MoreTopics{All topics covered?}
    
    CheckUnderstand -->|Partial understanding| Partial[Probe for specific confusion]
    Partial --> Alternative[Use alternative explanation / analogy]
    Alternative --> CheckUnderstand
    
    CheckUnderstand -->|Misconception| MisconceptionID[Identify root misconception]
    MisconceptionID --> Scaffold[Break down into sub‑steps / guided practice]
    Scaffold --> CheckUnderstand
    
    CheckUnderstand -->|Completely lost| BreakDown[Break concept into smaller chunks]
    BreakDown --> Scaffold
    
    CheckUnderstand -->|Blank / unsure| Prompt[Ask probing questions]
    Prompt --> CheckUnderstand

    MoreTopics -->|No| NextTopic
    
    MoreTopics -->|Yes| Review[Comprehensive review & summary]
    
    %% === 3. INTERLEAVING ===
    Review --> Interleave[<b>Interleaved Practice</b><br/>Mix problems from different topics]
    Interleave --> FinalAssess[Assess overall learning:<br/>application problem]
    
    FinalAssess --> Mastery{Mastery achieved?}
    Mastery -->|Yes| Feedback[Provide positive feedback & summary]
    
    Mastery -->|No| Weaknesses[Identify weak areas]
    Weaknesses --> Plan[Create targeted improvement plan]
    
    %% === SPACED RETRIEVAL (Scheduling) ===
    Plan --> SpacedSchedule[<b>Spaced Repetition Schedule</b><br/>Plan future review sessions: tomorrow, next week]
    SpacedSchedule --> Feedback
    
    Feedback --> NextSteps[Agree on next steps / practice]
    NextSteps --> End([End session])

    %% Engagement & fatigue monitoring
    CheckUnderstand -.-> Fatigue{Signs of fatigue<br/>or distraction?}
    Fatigue -->|Yes| Break[Short break / change activity]
    Break --> Present
    
    Fatigue -->|No| CheckUnderstand
    
    %% Motivation boosters
    Alternative -.-> Encouragement[Encourage & affirm effort]
    Encouragement --> CheckUnderstand
    
    BreakDown -.-> Encouragement
    
    %% === FEEDBACK LOOPS for New Techniques ===
    ActiveRecall -.-> FeedbackRecall[Emphasize retrieval effort strengthens memory]
    FeedbackRecall --> ActiveRecall
    
    Interleave -.-> MetaCognition[Prompt: 'Which method applies here?']
    MetaCognition --> Interleave
    
    SpacedInit --> SpacedReminder[During break, quickly revisit noted topic]
    SpacedReminder --> NextTopic