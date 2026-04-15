"""
Anilla AI Knowledge Base
========================

Medical knowledge base derived from MedQuAD-style data for the Anilla clinic
scheduling system. This module contains NON-PHI reference data used by the
symptom extractor, question engine, and report generator.

All symptom-condition mappings are medically plausible but simplified for a
scheduling triage context. They are NOT intended for clinical diagnosis.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SYMPTOM -> CONDITION MAP
# ---------------------------------------------------------------------------
# Each symptom maps to a list of (condition, prior_probability) tuples.
# Probabilities are rough priors for a primary-care population and do NOT
# sum to 1.0 -- they represent independent likelihoods used for ranking.
# ---------------------------------------------------------------------------

SYMPTOM_CONDITION_MAP: dict[str, list[tuple[str, float]]] = {
    # --- Head / Neurological ---
    "headache": [
        ("tension_headache", 0.45),
        ("migraine", 0.25),
        ("sinusitis", 0.12),
        ("hypertension", 0.08),
        ("cluster_headache", 0.03),
        ("meningitis", 0.02),
        ("intracranial_mass", 0.01),
    ],
    "dizziness": [
        ("benign_positional_vertigo", 0.30),
        ("orthostatic_hypotension", 0.20),
        ("vestibular_neuritis", 0.12),
        ("anemia", 0.10),
        ("anxiety_disorder", 0.10),
        ("cardiac_arrhythmia", 0.06),
        ("hypoglycemia", 0.05),
        ("stroke", 0.02),
    ],

    # --- Cardiovascular / Respiratory ---
    "chest_pain": [
        ("musculoskeletal_chest_pain", 0.35),
        ("gastroesophageal_reflux", 0.20),
        ("angina_pectoris", 0.12),
        ("costochondritis", 0.10),
        ("panic_attack", 0.08),
        ("pneumonia", 0.05),
        ("pulmonary_embolism", 0.03),
        ("acute_coronary_syndrome", 0.03),
        ("aortic_dissection", 0.01),
    ],
    "shortness_of_breath": [
        ("asthma", 0.25),
        ("copd_exacerbation", 0.15),
        ("anxiety_disorder", 0.15),
        ("heart_failure", 0.10),
        ("pneumonia", 0.10),
        ("anemia", 0.08),
        ("pulmonary_embolism", 0.04),
        ("interstitial_lung_disease", 0.03),
    ],
    "cough": [
        ("upper_respiratory_infection", 0.35),
        ("allergic_rhinitis", 0.15),
        ("asthma", 0.12),
        ("gastroesophageal_reflux", 0.10),
        ("acute_bronchitis", 0.10),
        ("pneumonia", 0.06),
        ("copd_exacerbation", 0.05),
        ("lung_cancer", 0.01),
    ],
    "palpitations": [
        ("anxiety_disorder", 0.30),
        ("premature_atrial_contractions", 0.20),
        ("atrial_fibrillation", 0.12),
        ("hyperthyroidism", 0.10),
        ("anemia", 0.08),
        ("cardiac_arrhythmia", 0.08),
        ("mitral_valve_prolapse", 0.05),
    ],

    # --- Gastrointestinal ---
    "abdominal_pain": [
        ("gastritis", 0.18),
        ("irritable_bowel_syndrome", 0.15),
        ("gastroesophageal_reflux", 0.12),
        ("constipation", 0.10),
        ("urinary_tract_infection", 0.08),
        ("gallstone_disease", 0.07),
        ("appendicitis", 0.05),
        ("peptic_ulcer", 0.05),
        ("inflammatory_bowel_disease", 0.04),
        ("pancreatitis", 0.03),
        ("ovarian_cyst", 0.03),
    ],
    "nausea": [
        ("gastritis", 0.20),
        ("gastroesophageal_reflux", 0.15),
        ("migraine", 0.12),
        ("pregnancy", 0.10),
        ("medication_side_effect", 0.10),
        ("gallstone_disease", 0.06),
        ("appendicitis", 0.04),
        ("labyrinthitis", 0.04),
    ],

    # --- Musculoskeletal ---
    "back_pain": [
        ("lumbar_strain", 0.40),
        ("degenerative_disc_disease", 0.18),
        ("herniated_disc", 0.12),
        ("osteoarthritis", 0.08),
        ("spinal_stenosis", 0.06),
        ("kidney_stone", 0.05),
        ("ankylosing_spondylitis", 0.03),
        ("vertebral_compression_fracture", 0.02),
    ],
    "herniated_disc": [
        ("herniated_disc", 0.70),
        ("spinal_stenosis", 0.15),
        ("degenerative_disc_disease", 0.10),
        ("sciatica", 0.30),
        ("radiculopathy", 0.25),
    ],
    "joint_pain": [
        ("osteoarthritis", 0.30),
        ("rheumatoid_arthritis", 0.12),
        ("gout", 0.10),
        ("tendinitis", 0.10),
        ("bursitis", 0.08),
        ("fibromyalgia", 0.07),
        ("lupus", 0.04),
        ("lyme_disease", 0.03),
        ("septic_arthritis", 0.02),
    ],
    "neck_pain": [
        ("cervical_strain", 0.40),
        ("cervical_spondylosis", 0.20),
        ("tension_headache", 0.10),
        ("herniated_disc", 0.08),
        ("meningitis", 0.03),
        ("fibromyalgia", 0.05),
    ],

    # --- Systemic ---
    "fatigue": [
        ("anemia", 0.15),
        ("hypothyroidism", 0.12),
        ("depression", 0.15),
        ("sleep_apnea", 0.10),
        ("diabetes_mellitus", 0.08),
        ("chronic_fatigue_syndrome", 0.06),
        ("heart_failure", 0.04),
        ("fibromyalgia", 0.05),
        ("vitamin_d_deficiency", 0.08),
        ("medication_side_effect", 0.06),
    ],
    "fever": [
        ("upper_respiratory_infection", 0.30),
        ("urinary_tract_infection", 0.12),
        ("influenza", 0.15),
        ("pneumonia", 0.08),
        ("acute_bronchitis", 0.07),
        ("cellulitis", 0.05),
        ("appendicitis", 0.03),
        ("meningitis", 0.02),
        ("endocarditis", 0.01),
    ],
    "weight_changes": [
        ("hypothyroidism", 0.15),
        ("hyperthyroidism", 0.12),
        ("diabetes_mellitus", 0.12),
        ("depression", 0.15),
        ("medication_side_effect", 0.10),
        ("cushing_syndrome", 0.03),
        ("malignancy", 0.03),
        ("eating_disorder", 0.05),
    ],

    # --- Dermatological ---
    "skin_rash": [
        ("contact_dermatitis", 0.25),
        ("eczema", 0.18),
        ("psoriasis", 0.10),
        ("allergic_reaction", 0.12),
        ("fungal_infection", 0.10),
        ("urticaria", 0.08),
        ("cellulitis", 0.04),
        ("lupus", 0.03),
        ("shingles", 0.04),
    ],

    # --- Urological ---
    "urinary_issues": [
        ("urinary_tract_infection", 0.35),
        ("benign_prostatic_hyperplasia", 0.15),
        ("overactive_bladder", 0.12),
        ("kidney_stone", 0.08),
        ("interstitial_cystitis", 0.06),
        ("sexually_transmitted_infection", 0.05),
        ("diabetes_mellitus", 0.04),
        ("prostate_cancer", 0.02),
    ],

    # --- Mental Health ---
    "anxiety": [
        ("generalized_anxiety_disorder", 0.35),
        ("panic_disorder", 0.15),
        ("social_anxiety_disorder", 0.10),
        ("hyperthyroidism", 0.06),
        ("medication_side_effect", 0.05),
        ("ptsd", 0.08),
        ("depression", 0.10),
    ],
    "depression": [
        ("major_depressive_disorder", 0.40),
        ("adjustment_disorder", 0.15),
        ("bipolar_disorder", 0.08),
        ("hypothyroidism", 0.06),
        ("vitamin_d_deficiency", 0.05),
        ("substance_use_disorder", 0.05),
        ("grief_reaction", 0.08),
    ],
    "sleep_problems": [
        ("insomnia", 0.30),
        ("sleep_apnea", 0.18),
        ("anxiety_disorder", 0.15),
        ("depression", 0.12),
        ("restless_leg_syndrome", 0.08),
        ("medication_side_effect", 0.06),
        ("hyperthyroidism", 0.04),
    ],

    # --- ENT ---
    "sore_throat": [
        ("viral_pharyngitis", 0.40),
        ("strep_pharyngitis", 0.20),
        ("allergic_rhinitis", 0.10),
        ("gastroesophageal_reflux", 0.08),
        ("mononucleosis", 0.05),
        ("tonsillitis", 0.08),
    ],
    "ear_pain": [
        ("otitis_media", 0.30),
        ("otitis_externa", 0.20),
        ("eustachian_tube_dysfunction", 0.15),
        ("temporomandibular_disorder", 0.12),
        ("referred_dental_pain", 0.08),
    ],

    # --- Ophthalmological ---
    "vision_changes": [
        ("refractive_error", 0.30),
        ("dry_eye_syndrome", 0.15),
        ("cataracts", 0.10),
        ("glaucoma", 0.08),
        ("diabetic_retinopathy", 0.06),
        ("migraine_with_aura", 0.08),
        ("macular_degeneration", 0.05),
        ("retinal_detachment", 0.02),
    ],

    # --- Additional common symptoms ---
    "numbness_tingling": [
        ("carpal_tunnel_syndrome", 0.25),
        ("peripheral_neuropathy", 0.18),
        ("herniated_disc", 0.12),
        ("diabetes_mellitus", 0.10),
        ("vitamin_b12_deficiency", 0.08),
        ("multiple_sclerosis", 0.04),
        ("stroke", 0.03),
    ],
    "swelling": [
        ("edema", 0.20),
        ("heart_failure", 0.10),
        ("deep_vein_thrombosis", 0.08),
        ("kidney_disease", 0.08),
        ("cellulitis", 0.10),
        ("allergic_reaction", 0.10),
        ("sprain_strain", 0.15),
        ("gout", 0.06),
    ],
    "bruising_bleeding": [
        ("medication_side_effect", 0.25),
        ("thrombocytopenia", 0.12),
        ("vitamin_k_deficiency", 0.08),
        ("liver_disease", 0.08),
        ("von_willebrand_disease", 0.05),
        ("leukemia", 0.03),
    ],
    "foot_pain": [
        ("plantar_fasciitis", 0.25),
        ("diabetic_neuropathy", 0.20),
        ("peripheral_arterial_disease", 0.15),
        ("gout", 0.15),
        ("osteoarthritis", 0.12),
        ("stress_fracture", 0.08),
    ],
}


# ---------------------------------------------------------------------------
# CONDITION -> FOLLOW-UP QUESTIONS
# ---------------------------------------------------------------------------
# Each condition has a list of follow-up questions used by the question engine
# to narrow the differential. question_type is "yes_no" or "short_answer".
# ---------------------------------------------------------------------------

CONDITION_QUESTIONS: dict[str, list[dict]] = {
    "tension_headache": [
        {"id": "th_location", "text": "Is the pain on both sides of your head, like a band or pressure?", "question_type": "yes_no", "weight": 0.8},
        {"id": "th_stress", "text": "Have you been under more stress than usual recently?", "question_type": "yes_no", "weight": 0.5},
        {"id": "th_duration", "text": "How long does each headache episode typically last?", "question_type": "short_answer", "weight": 0.6},
    ],
    "migraine": [
        {"id": "mi_one_side", "text": "Is the pain usually on one side of your head?", "question_type": "yes_no", "weight": 0.8},
        {"id": "mi_nausea", "text": "Do you experience nausea or vomiting with the headache?", "question_type": "yes_no", "weight": 0.7},
        {"id": "mi_light", "text": "Does light or sound make the headache worse?", "question_type": "yes_no", "weight": 0.7},
        {"id": "mi_aura", "text": "Do you see flashing lights or zigzag lines before the headache starts?", "question_type": "yes_no", "weight": 0.6},
    ],
    "sinusitis": [
        {"id": "si_face_pressure", "text": "Do you feel pressure or pain around your cheeks, forehead, or eyes?", "question_type": "yes_no", "weight": 0.8},
        {"id": "si_nasal", "text": "Do you have nasal congestion or thick nasal discharge?", "question_type": "yes_no", "weight": 0.7},
        {"id": "si_duration", "text": "How long have you had these symptoms?", "question_type": "short_answer", "weight": 0.5},
    ],
    "hypertension": [
        {"id": "ht_known", "text": "Have you been diagnosed with high blood pressure before?", "question_type": "yes_no", "weight": 0.9},
        {"id": "ht_meds", "text": "Are you currently taking any blood pressure medications?", "question_type": "yes_no", "weight": 0.7},
        {"id": "ht_recent_bp", "text": "Do you know your most recent blood pressure reading?", "question_type": "short_answer", "weight": 0.6},
    ],
    "angina_pectoris": [
        {"id": "ap_exertion", "text": "Does the chest pain come on with physical activity or exertion?", "question_type": "yes_no", "weight": 0.9},
        {"id": "ap_rest_relief", "text": "Does the pain go away when you rest?", "question_type": "yes_no", "weight": 0.8},
        {"id": "ap_radiation", "text": "Does the pain spread to your arm, jaw, or back?", "question_type": "yes_no", "weight": 0.7},
        {"id": "ap_duration", "text": "How long does each episode of chest pain typically last?", "question_type": "short_answer", "weight": 0.6},
    ],
    "gastroesophageal_reflux": [
        {"id": "gerd_burn", "text": "Do you experience a burning sensation in your chest or throat?", "question_type": "yes_no", "weight": 0.8},
        {"id": "gerd_food", "text": "Does eating or lying down make the symptoms worse?", "question_type": "yes_no", "weight": 0.7},
        {"id": "gerd_taste", "text": "Do you notice an acid or bitter taste in your mouth?", "question_type": "yes_no", "weight": 0.6},
    ],
    "asthma": [
        {"id": "as_wheeze", "text": "Do you hear wheezing when you breathe?", "question_type": "yes_no", "weight": 0.8},
        {"id": "as_trigger", "text": "Are there specific triggers like exercise, cold air, or allergens?", "question_type": "short_answer", "weight": 0.7},
        {"id": "as_history", "text": "Have you been diagnosed with asthma before?", "question_type": "yes_no", "weight": 0.9},
        {"id": "as_inhaler", "text": "Do you use an inhaler? If so, how often?", "question_type": "short_answer", "weight": 0.6},
    ],
    "anemia": [
        {"id": "an_pale", "text": "Have you noticed that you look paler than usual?", "question_type": "yes_no", "weight": 0.5},
        {"id": "an_diet", "text": "How would you describe your diet, particularly iron-rich foods?", "question_type": "short_answer", "weight": 0.6},
        {"id": "an_periods", "text": "If applicable, are your menstrual periods heavy?", "question_type": "yes_no", "weight": 0.7},
        {"id": "an_blood", "text": "Have you noticed any blood in your stool or dark/tarry stools?", "question_type": "yes_no", "weight": 0.8},
    ],
    "hypothyroidism": [
        {"id": "hy_cold", "text": "Do you feel cold more often than others around you?", "question_type": "yes_no", "weight": 0.6},
        {"id": "hy_weight", "text": "Have you gained weight without a clear reason?", "question_type": "yes_no", "weight": 0.7},
        {"id": "hy_constipation", "text": "Have you been experiencing constipation?", "question_type": "yes_no", "weight": 0.5},
        {"id": "hy_history", "text": "Have you ever been diagnosed with a thyroid condition?", "question_type": "yes_no", "weight": 0.9},
    ],
    "diabetes_mellitus": [
        {"id": "dm_thirst", "text": "Have you been unusually thirsty or urinating more frequently?", "question_type": "yes_no", "weight": 0.8},
        {"id": "dm_family", "text": "Does diabetes run in your family?", "question_type": "yes_no", "weight": 0.6},
        {"id": "dm_history", "text": "Have you been diagnosed with diabetes or pre-diabetes?", "question_type": "yes_no", "weight": 0.9},
        {"id": "dm_a1c", "text": "Do you know your last A1C or blood sugar level?", "question_type": "short_answer", "weight": 0.7},
    ],
    "urinary_tract_infection": [
        {"id": "uti_burn", "text": "Do you feel burning or pain when you urinate?", "question_type": "yes_no", "weight": 0.8},
        {"id": "uti_freq", "text": "Are you urinating more frequently than normal?", "question_type": "yes_no", "weight": 0.7},
        {"id": "uti_blood", "text": "Have you noticed blood in your urine?", "question_type": "yes_no", "weight": 0.6},
        {"id": "uti_history", "text": "Have you had urinary tract infections before?", "question_type": "yes_no", "weight": 0.5},
    ],
    "major_depressive_disorder": [
        {"id": "mdd_safety", "text": "Are you having any thoughts of hurting yourself or suicide?", "question_type": "yes_no", "weight": 0.95},
        {"id": "mdd_interest", "text": "Have you lost interest in activities you used to enjoy?", "question_type": "yes_no", "weight": 0.8},
        {"id": "mdd_duration", "text": "How long have you been feeling this way?", "question_type": "short_answer", "weight": 0.7},
        {"id": "mdd_sleep", "text": "Have your sleep patterns changed — trouble falling asleep, staying asleep, or sleeping too much?", "question_type": "yes_no", "weight": 0.6},
        {"id": "mdd_concentration", "text": "Are you having difficulty concentrating or making decisions?", "question_type": "yes_no", "weight": 0.6},
        {"id": "mdd_energy", "text": "Do you feel persistently tired or low on energy, even after rest?", "question_type": "yes_no", "weight": 0.6},
        {"id": "mdd_appetite", "text": "Have you noticed significant changes in your appetite or weight?", "question_type": "yes_no", "weight": 0.5},
        {"id": "mdd_worthless", "text": "Do you find yourself feeling worthless or excessively guilty?", "question_type": "yes_no", "weight": 0.5},
        {"id": "mdd_function", "text": "How much are these feelings affecting your work, relationships, or daily activities?", "question_type": "short_answer", "weight": 0.6},
        {"id": "mdd_history", "text": "Have you experienced episodes like this before, or been diagnosed with depression or a mood disorder?", "question_type": "yes_no", "weight": 0.5},
    ],
    "generalized_anxiety_disorder": [
        {"id": "gad_worry", "text": "Do you find it difficult to control your worrying?", "question_type": "yes_no", "weight": 0.8},
        {"id": "gad_restless", "text": "Do you feel restless or on edge most days?", "question_type": "yes_no", "weight": 0.7},
        {"id": "gad_physical", "text": "Do you experience muscle tension, racing heart, or trembling?", "question_type": "yes_no", "weight": 0.6},
        {"id": "gad_duration", "text": "How long have you been experiencing these feelings?", "question_type": "short_answer", "weight": 0.5},
    ],
    "osteoarthritis": [
        {"id": "oa_stiffness", "text": "Do you experience joint stiffness, especially in the morning?", "question_type": "yes_no", "weight": 0.7},
        {"id": "oa_worse_activity", "text": "Does the pain get worse with activity and improve with rest?", "question_type": "yes_no", "weight": 0.8},
        {"id": "oa_which_joints", "text": "Which joints are affected?", "question_type": "short_answer", "weight": 0.6},
        {"id": "oa_crepitus", "text": "Do you hear or feel grinding or crackling in the joint?", "question_type": "yes_no", "weight": 0.5},
    ],
    "lumbar_strain": [
        {"id": "ls_onset", "text": "Did the pain start after lifting, bending, or a specific activity?", "question_type": "yes_no", "weight": 0.8},
        {"id": "ls_radiation", "text": "Does the pain go down into your legs?", "question_type": "yes_no", "weight": 0.7},
        {"id": "ls_numbness", "text": "Do you have any numbness, tingling, or weakness in your legs?", "question_type": "yes_no", "weight": 0.8},
    ],
    "pneumonia": [
        {"id": "pn_fever", "text": "Do you have a fever or chills?", "question_type": "yes_no", "weight": 0.7},
        {"id": "pn_productive", "text": "Are you coughing up phlegm? If so, what color?", "question_type": "short_answer", "weight": 0.7},
        {"id": "pn_breathing", "text": "Are you having difficulty breathing, even at rest?", "question_type": "yes_no", "weight": 0.8},
    ],
    "upper_respiratory_infection": [
        {"id": "uri_duration", "text": "How many days have you had symptoms?", "question_type": "short_answer", "weight": 0.6},
        {"id": "uri_congestion", "text": "Do you have nasal congestion or a runny nose?", "question_type": "yes_no", "weight": 0.5},
        {"id": "uri_throat", "text": "Do you have a sore throat?", "question_type": "yes_no", "weight": 0.5},
    ],
    "contact_dermatitis": [
        {"id": "cd_location", "text": "Where on your body is the rash?", "question_type": "short_answer", "weight": 0.7},
        {"id": "cd_new_product", "text": "Have you started using any new products, soaps, or detergents recently?", "question_type": "yes_no", "weight": 0.8},
        {"id": "cd_itch", "text": "Is the rash itchy?", "question_type": "yes_no", "weight": 0.6},
    ],
    "allergic_reaction": [
        {"id": "ar_trigger", "text": "Can you identify what might have triggered the reaction?", "question_type": "short_answer", "weight": 0.8},
        {"id": "ar_breathing", "text": "Are you having any difficulty breathing or swelling of your face/throat?", "question_type": "yes_no", "weight": 0.9},
        {"id": "ar_history", "text": "Do you have known allergies?", "question_type": "yes_no", "weight": 0.7},
    ],
    "kidney_stone": [
        {"id": "ks_location", "text": "Is the pain in your side or lower back, and does it come in waves?", "question_type": "yes_no", "weight": 0.8},
        {"id": "ks_blood", "text": "Have you noticed blood in your urine?", "question_type": "yes_no", "weight": 0.7},
        {"id": "ks_history", "text": "Have you had kidney stones before?", "question_type": "yes_no", "weight": 0.6},
    ],
    "sleep_apnea": [
        {"id": "sa_snore", "text": "Have you been told that you snore loudly?", "question_type": "yes_no", "weight": 0.7},
        {"id": "sa_stop", "text": "Has anyone observed you stop breathing during sleep?", "question_type": "yes_no", "weight": 0.9},
        {"id": "sa_tired", "text": "Do you feel excessively tired during the day despite sleeping?", "question_type": "yes_no", "weight": 0.7},
    ],
    "heart_failure": [
        {"id": "hf_edema", "text": "Do you notice swelling in your ankles or legs?", "question_type": "yes_no", "weight": 0.7},
        {"id": "hf_orthopnea", "text": "Do you need extra pillows or to sit up to breathe comfortably at night?", "question_type": "yes_no", "weight": 0.8},
        {"id": "hf_exertion", "text": "Do you get short of breath with activities that were previously easy?", "question_type": "yes_no", "weight": 0.8},
    ],
    "irritable_bowel_syndrome": [
        {"id": "ibs_pattern", "text": "Do your symptoms include alternating constipation and diarrhea?", "question_type": "yes_no", "weight": 0.7},
        {"id": "ibs_food", "text": "Are there specific foods that seem to trigger your symptoms?", "question_type": "short_answer", "weight": 0.6},
        {"id": "ibs_stress", "text": "Do your symptoms get worse during periods of stress?", "question_type": "yes_no", "weight": 0.6},
    ],
    "fibromyalgia": [
        {"id": "fm_widespread", "text": "Is the pain widespread, affecting multiple areas of your body?", "question_type": "yes_no", "weight": 0.8},
        {"id": "fm_fatigue", "text": "Do you experience significant fatigue along with the pain?", "question_type": "yes_no", "weight": 0.7},
        {"id": "fm_cognitive", "text": "Do you have difficulty with memory or concentration (sometimes called 'brain fog')?", "question_type": "yes_no", "weight": 0.6},
    ],
    "gout": [
        {"id": "gt_toe", "text": "Is the pain in your big toe?", "question_type": "yes_no", "weight": 0.8},
        {"id": "gt_sudden", "text": "Did the pain come on suddenly, perhaps overnight?", "question_type": "yes_no", "weight": 0.7},
        {"id": "gt_red_hot", "text": "Is the affected joint red, hot, and swollen?", "question_type": "yes_no", "weight": 0.7},
    ],
    "panic_disorder": [
        {"id": "pd_episodes", "text": "Do you experience sudden episodes of intense fear or discomfort?", "question_type": "yes_no", "weight": 0.8},
        {"id": "pd_physical", "text": "During these episodes, do you have racing heart, sweating, or trembling?", "question_type": "yes_no", "weight": 0.7},
        {"id": "pd_worry_next", "text": "Do you worry about when the next episode will happen?", "question_type": "yes_no", "weight": 0.6},
    ],
    "atrial_fibrillation": [
        {"id": "af_irregular", "text": "Does your heartbeat feel irregular or chaotic, not just fast?", "question_type": "yes_no", "weight": 0.8},
        {"id": "af_lightheaded", "text": "Do you feel lightheaded or faint during episodes?", "question_type": "yes_no", "weight": 0.6},
        {"id": "af_duration", "text": "How long do the episodes of rapid or irregular heartbeat last?", "question_type": "short_answer", "weight": 0.5},
    ],
    "benign_positional_vertigo": [
        {"id": "bpv_position", "text": "Does the dizziness occur when you change head position, like rolling over in bed?", "question_type": "yes_no", "weight": 0.9},
        {"id": "bpv_duration_episode", "text": "Does each episode of spinning last less than a minute?", "question_type": "yes_no", "weight": 0.7},
        {"id": "bpv_nausea", "text": "Do you feel nauseous during the spinning episodes?", "question_type": "yes_no", "weight": 0.5},
    ],
    "carpal_tunnel_syndrome": [
        {"id": "cts_hand", "text": "Is the numbness or tingling mainly in your thumb, index, and middle fingers?", "question_type": "yes_no", "weight": 0.8},
        {"id": "cts_night", "text": "Do symptoms wake you up at night?", "question_type": "yes_no", "weight": 0.7},
        {"id": "cts_work", "text": "Does your work involve repetitive hand or wrist movements?", "question_type": "yes_no", "weight": 0.6},
    ],
    "insomnia": [
        {"id": "in_onset", "text": "Do you have difficulty falling asleep, staying asleep, or both?", "question_type": "short_answer", "weight": 0.7},
        {"id": "in_duration", "text": "How long have you been experiencing sleep difficulties?", "question_type": "short_answer", "weight": 0.6},
        {"id": "in_habits", "text": "Do you use screens or caffeine close to bedtime?", "question_type": "yes_no", "weight": 0.5},
    ],
    "herniated_disc": [
        {"id": "hd_radiation", "text": "Does the pain radiate down your leg or arm?", "question_type": "yes_no", "weight": 0.9},
        {"id": "hd_numbness", "text": "Do you have any numbness, tingling, or weakness in your legs or feet?", "question_type": "yes_no", "weight": 0.9},
        {"id": "hd_bladder", "text": "Have you had any difficulty with bladder or bowel control?", "question_type": "yes_no", "weight": 0.95},
        {"id": "hd_worse_sitting", "text": "Does the pain worsen when sitting or bending forward?", "question_type": "yes_no", "weight": 0.7},
        {"id": "hd_onset", "text": "Did the pain start after a specific injury or activity, or come on gradually?", "question_type": "short_answer", "weight": 0.7},
        {"id": "hd_treatment", "text": "Have you tried any treatments such as physical therapy, injections, or surgery?", "question_type": "short_answer", "weight": 0.6},
        {"id": "hd_duration", "text": "How long have you been experiencing this?", "question_type": "short_answer", "weight": 0.6},
        {"id": "hd_severity", "text": "On a scale of 1 to 10, how would you rate the pain on an average day?", "question_type": "short_answer", "weight": 0.7},
        {"id": "hd_daily_impact", "text": "How much is this affecting your ability to work or do daily activities?", "question_type": "short_answer", "weight": 0.6},
        {"id": "hd_imaging", "text": "Have you had any imaging done, such as an MRI or X-ray?", "question_type": "yes_no", "weight": 0.5},
    ],
    "sciatica": [
        {"id": "sc_path", "text": "Does the pain travel from your lower back through your buttock and down your leg?", "question_type": "yes_no", "weight": 0.9},
        {"id": "sc_one_side", "text": "Is the pain on one side only?", "question_type": "yes_no", "weight": 0.7},
        {"id": "sc_worse_sit", "text": "Does sitting or driving make the pain worse?", "question_type": "yes_no", "weight": 0.7},
        {"id": "sc_numbness", "text": "Do you have numbness or tingling in your leg or foot?", "question_type": "yes_no", "weight": 0.8},
    ],
    "radiculopathy": [
        {"id": "rp_weakness", "text": "Do you have any muscle weakness in your arm or leg?", "question_type": "yes_no", "weight": 0.8},
        {"id": "rp_sharp", "text": "Is the pain sharp, shooting, or electric-shock-like?", "question_type": "yes_no", "weight": 0.7},
        {"id": "rp_neck_back", "text": "Is the pain coming from your neck or lower back?", "question_type": "short_answer", "weight": 0.6},
    ],
    "spinal_stenosis": [
        {"id": "ss_walking", "text": "Does walking cause pain or weakness in your legs that goes away when you sit or lean forward?", "question_type": "yes_no", "weight": 0.9},
        {"id": "ss_bilateral", "text": "Are both legs affected?", "question_type": "yes_no", "weight": 0.7},
        {"id": "ss_history", "text": "Have you been diagnosed with spinal stenosis before?", "question_type": "yes_no", "weight": 0.8},
    ],
    "degenerative_disc_disease": [
        {"id": "ddd_chronic", "text": "Has the pain been ongoing for months or years rather than a recent onset?", "question_type": "yes_no", "weight": 0.8},
        {"id": "ddd_worse_morning", "text": "Is the pain worse in the morning or after periods of inactivity?", "question_type": "yes_no", "weight": 0.6},
        {"id": "ddd_age", "text": "Have you been told that age-related changes to your spine are a factor?", "question_type": "yes_no", "weight": 0.5},
    ],
    "peripheral_arterial_disease": [
        {"id": "pad_diabetes", "text": "Do you have diabetes or a history of high blood sugar?", "question_type": "yes_no", "weight": 0.95},
        {"id": "pad_claudication", "text": "Does the pain or cramping in your foot or leg come on when you walk and ease when you rest?", "question_type": "yes_no", "weight": 0.90},
        {"id": "pad_cold", "text": "Does your foot feel cold or look pale or bluish compared to the other one?", "question_type": "yes_no", "weight": 0.85},
        {"id": "pad_wound", "text": "Do you have any sores, ulcers, or wounds on your foot or lower leg that are slow to heal?", "question_type": "yes_no", "weight": 0.90},
        {"id": "pad_smoking", "text": "Do you smoke or have you smoked in the past?", "question_type": "yes_no", "weight": 0.60},
    ],
    "diabetic_neuropathy": [
        {"id": "dn_diabetes_known", "text": "Have you been diagnosed with diabetes?", "question_type": "yes_no", "weight": 0.95},
        {"id": "dn_burning", "text": "Do you feel a burning, shooting, or electric-shock pain in your feet?", "question_type": "yes_no", "weight": 0.85},
        {"id": "dn_numbness", "text": "Do you have numbness or reduced sensation in your feet — for example, difficulty feeling temperature or touch?", "question_type": "yes_no", "weight": 0.85},
        {"id": "dn_worse_night", "text": "Is the pain or discomfort worse at night?", "question_type": "yes_no", "weight": 0.70},
        {"id": "dn_a1c", "text": "How well has your blood sugar been controlled recently — do you know your last A1C?", "question_type": "short_answer", "weight": 0.65},
    ],
    "plantar_fasciitis": [
        {"id": "pf_heel", "text": "Is the pain mainly in your heel, especially the bottom of your foot?", "question_type": "yes_no", "weight": 0.85},
        {"id": "pf_morning", "text": "Is it worst when you take your first steps in the morning or after sitting for a while?", "question_type": "yes_no", "weight": 0.85},
        {"id": "pf_standing", "text": "Does prolonged standing or walking make it worse?", "question_type": "yes_no", "weight": 0.70},
    ],
}


# ---------------------------------------------------------------------------
# RED FLAG PATTERNS
# ---------------------------------------------------------------------------
# Symptom combinations that require immediate clinical attention. The question
# engine checks these after every answer update. Severity levels:
#   "critical"  -> suggest ER / call 911
#   "high"      -> same-day physician evaluation
#   "moderate"  -> expedited scheduling (within 24-48h)
# ---------------------------------------------------------------------------

RED_FLAG_PATTERNS: list[dict] = [
    # -----------------------------------------------------------------------
    # CRITICAL — call 911 / immediate ER
    # -----------------------------------------------------------------------
    {
        "id": "rf_acs",
        "name": "Possible acute coronary syndrome",
        # ANY one of these symptoms + at least one indicator triggers the flag.
        # Palpitations added so isolated ACS presenting with arrhythmia is captured.
        "symptoms": ["chest_pain", "shortness_of_breath", "palpitations"],
        "additional_indicators": [
            "radiating arm pain", "radiating to arm", "left arm pain", "left arm",
            "pain in my arm", "arm hurts", "arm ache",
            "jaw pain", "jaw tightness", "pain in my jaw",
            "sweating profusely", "cold sweat", "breaking out in sweat", "drenched in sweat",
            "nausea", "vomiting", "feel sick",
            "pressure in chest", "squeezing chest", "crushing chest",
            "tightness in chest", "heavy chest", "elephant on my chest",
            "worse with exertion", "pain when i walk", "pain when i climb stairs",
        ],
        "severity": "critical",
        "action": "Advise calling 911 or going to nearest ER immediately.",
    },
    {
        "id": "rf_aortic_dissection",
        "name": "Possible aortic dissection",
        # Tearing/ripping chest or back pain at maximum intensity from onset —
        # distinct from ACS. Back pain anchor catches posterior dissections that
        # never involve typical chest pain.
        "symptoms": ["chest_pain", "back_pain"],
        "additional_indicators": [
            "tearing", "ripping", "tearing pain", "ripping pain",
            "like something tore", "like something ripped", "like a knife",
            "sudden severe", "instant onset", "maximum from the start", "worst from the beginning",
            "radiating to back", "going through to my back", "through to my back",
            "radiating to jaw", "worst pain of my life", "worst pain ever",
            "different blood pressure", "one arm higher",
        ],
        "severity": "critical",
        "action": "Advise calling 911 immediately. Aortic dissection is a surgical emergency — time-critical.",
    },
    {
        "id": "rf_hypertensive_emergency",
        "name": "Possible hypertensive emergency",
        # Very high BP plus end-organ symptoms (headache, vision, chest, confusion).
        # BP numbers are matched as substrings in free text (e.g. "190/110").
        "symptoms": ["headache", "vision_changes", "chest_pain"],
        "additional_indicators": [
            "very high blood pressure", "extremely high blood pressure", "dangerously high blood pressure",
            "blood pressure over 180", "blood pressure 190", "blood pressure 200",
            "blood pressure 210", "blood pressure 220", "blood pressure 230",
            "190/", "200/", "210/", "220/", "230/", "180/12",
            "hypertensive crisis", "hypertensive emergency",
            "worst headache", "thunderclap", "sudden severe headache", "worst headache of my life",
            "blurred vision", "can't see straight", "vision going blurry",
            "confused", "can't think straight", "not making sense",
            "nosebleed", "nose won't stop bleeding",
        ],
        "severity": "critical",
        "action": "Advise urgent ER evaluation. Hypertensive emergency can cause stroke, heart attack, or kidney failure.",
    },
    {
        "id": "rf_aortic_aneurysm",
        "name": "Possible aortic aneurysm rupture",
        # Pulsating abdominal mass or sudden severe abdominal/back pain in a
        # high-risk patient (older male, hypertension, smoking history).
        "symptoms": ["abdominal_pain", "back_pain"],
        "additional_indicators": [
            "pulsating", "throbbing in my stomach", "throbbing in my abdomen",
            "can feel my heartbeat in my stomach", "can feel my pulse in my belly",
            "tearing", "ripping",
            "sudden severe abdominal", "sudden severe back",
            "worst stomach pain", "worst abdominal pain", "worst back pain ever",
            "aortic aneurysm", "aaa", "known aneurysm",
            "radiating to groin", "pain going to my legs", "flank pain",
        ],
        "severity": "critical",
        "action": "Advise calling 911 immediately. Ruptured AAA is a surgical emergency.",
    },
    {
        "id": "rf_suicidal",
        "name": "Suicidal ideation",
        # Empty symptoms list = symptom-independent: triggers on indicator match alone.
        # Suicidal ideation must NEVER be gated on prior symptom extraction.
        "symptoms": [],
        "additional_indicators": [
            "suicidal thoughts", "suicidal ideation", "suicidal",
            "self-harm", "self harm", "harm myself", "hurt myself", "hurting myself",
            "want to die", "wanting to die", "wish i was dead", "wish i were dead",
            "no reason to live", "not want to live", "not want to be here",
            "end my life", "end it all", "take my own life",
            "kill myself", "killing myself",
            "hopelessness",
            "mdd_safety",  # question_id: matches when patient answers "yes" to safety screen
        ],
        "severity": "critical",
        "action": "Provide crisis hotline (988). Flag for immediate clinical review.",
    },
    {
        "id": "rf_stroke_fast",
        "name": "Stroke signs (FAST)",
        # Previously only anchored to dizziness — many stroke patients present
        # with headache, vision change, or numbness/tingling as the primary
        # complaint. All four are now valid anchors.
        "symptoms": ["dizziness", "headache", "vision_changes", "numbness_tingling"],
        "additional_indicators": [
            "face drooping", "face is drooping", "face droop", "drooping face",
            "one side of face drooping", "face feels numb", "face went numb",
            "arm weakness", "arm went weak", "arm feels weak", "arm is weak",
            "can't lift my arm", "one arm weak", "arm numb", "arm went numb",
            "leg weakness", "leg went numb", "leg feels weak",
            "slurred speech", "can't speak", "trouble speaking", "words aren't coming out",
            "speech is slurred", "speaking funny", "can't get my words out",
            "sudden numbness", "suddenly went numb", "sudden weakness",
            "suddenly confused", "suddenly can't see", "vision went dark",
            "worst headache of my life", "worst headache ever", "thunderclap headache",
            "double vision", "vision suddenly changed",
        ],
        "severity": "critical",
        "action": "Advise calling 911 immediately. Stroke is time-critical — every minute matters.",
    },
    {
        "id": "rf_anaphylaxis",
        "name": "Severe allergic reaction / anaphylaxis",
        "symptoms": ["skin_rash"],
        "additional_indicators": [
            "throat swelling", "throat is closing", "throat feels tight", "throat closing up",
            "tongue swelling", "tongue feels big", "lip swelling", "lips swelling up",
            "can't breathe", "difficulty breathing", "hard to breathe",
            "high-pitched breathing", "wheezing", "whistling when breathing",
            "hives all over", "hives everywhere", "full body rash", "breaking out everywhere",
            "feeling faint", "going to pass out", "dizzy after eating", "dizzy after bee sting",
        ],
        "severity": "critical",
        "action": "Advise using EpiPen if available and calling 911.",
    },
    {
        "id": "rf_meningitis",
        "name": "Possible meningitis",
        "symptoms": ["fever", "headache"],
        "additional_indicators": [
            "stiff neck", "neck stiffness", "can't bend neck", "neck won't move", "neck is rigid",
            "light hurts my eyes", "can't look at light", "eyes hurt in light", "sensitive to light",
            "confused", "not making sense", "hard to wake up", "won't wake up",
            "purple spots", "tiny purple dots", "spots under skin", "spots that don't go away when pressed",
            "spots that don't fade", "dark spots all over",
        ],
        "severity": "critical",
        "action": "Advise going to ER immediately for evaluation.",
    },
    {
        "id": "rf_pe",
        "name": "Possible pulmonary embolism",
        # Cough added as anchor — PE can present with bloody cough and breathlessness
        # without prominent chest pain, which the original pattern would miss.
        "symptoms": ["shortness_of_breath", "chest_pain", "cough"],
        "additional_indicators": [
            "sudden shortness of breath", "suddenly can't breathe", "came on suddenly",
            "leg swelling", "one leg swollen", "calf pain", "calf swelling", "calf is sore",
            "recent surgery", "just had surgery", "recent travel", "long flight",
            "been in bed", "haven't been moving", "bed rest",
            "coughing up blood", "blood in spit", "blood when i cough", "bloody when i cough",
            "heart racing", "heart is going fast",
            "pain when i breathe", "hurts to breathe", "sharp pain breathing", "worse when i breathe",
        ],
        "severity": "critical",
        "action": "Advise ER evaluation. PE is time-critical.",
    },
    {
        "id": "rf_dka",
        "name": "Possible diabetic ketoacidosis (DKA)",
        # Nausea and fatigue are the most commonly extracted symptoms in early
        # DKA. Anchoring to both increases sensitivity without over-triggering.
        "symptoms": ["nausea", "fatigue"],
        "additional_indicators": [
            "fruity breath", "breath smells fruity", "breath smells sweet", "sweet-smelling breath",
            "breath smells like nail polish", "breath smells strange",
            "very high blood sugar", "blood sugar over 250", "blood sugar over 300",
            "blood sugar 300", "blood sugar 400", "sugar level really high",
            "ketones", "ketone", "tested for ketones", "ketones in urine",
            "not taking insulin", "missed insulin", "out of insulin", "ran out of insulin", "forgot insulin",
            "type 1 diabetes", "diabetic", "insulin dependent", "on insulin",
            "really thirsty", "drinking a lot of water", "can't stop drinking water",
            "peeing a lot", "going to the bathroom constantly",
            "vomiting and diabetic", "stomach pain and diabetic",
        ],
        "severity": "critical",
        "action": "Advise ER evaluation. DKA requires IV insulin and fluids — medical emergency.",
    },
    {
        "id": "rf_sepsis",
        "name": "Possible sepsis",
        "symptoms": ["fever"],
        "additional_indicators": [
            "confused", "not making sense", "acting strange", "hard to wake",
            "breathing really fast", "breathing rapidly",
            "heart going really fast", "heart racing",
            "blood pressure very low", "feel like passing out", "nearly passed out",
            "skin looks blotchy", "skin is mottled", "skin looks patchy",
            "shaking uncontrollably", "can't stop shaking", "violent shivers",
        ],
        "severity": "critical",
        "action": "Advise calling 911. Sepsis is time-critical.",
    },
    {
        "id": "rf_ectopic",
        "name": "Possible ectopic pregnancy",
        "symptoms": ["abdominal_pain"],
        "additional_indicators": [
            "missed period", "late period", "period is late", "haven't had my period",
            "positive pregnancy test", "think i'm pregnant", "might be pregnant",
            "vaginal bleeding", "bleeding down there", "spotting", "bleeding but pregnant",
            "shoulder pain", "pain in my shoulder", "tip of my shoulder hurts",
        ],
        "severity": "critical",
        "action": "Advise ER evaluation immediately.",
    },
    {
        "id": "rf_cauda_equina",
        "name": "Possible cauda equina syndrome",
        "symptoms": ["back_pain"],
        "additional_indicators": [
            "can't control my bowels", "had an accident", "bowel accident", "soiled myself",
            "can't control my bladder", "leaking urine", "can't hold my bladder",
            "can't pee", "can't urinate", "haven't been able to pee",
            "numbness in my groin", "numbness in my inner thighs", "numb between my legs",
            "numb in my bottom", "can't feel my bottom", "saddle area numb",
            "both legs gone weak", "both legs feel weak", "both legs numb",
        ],
        "severity": "critical",
        "action": "Advise ER immediately. Cauda equina is a surgical emergency.",
    },
    {
        "id": "rf_cardiac_syncope",
        "name": "Syncope — possible cardiac cause",
        # Escalated to critical: exertional or no-warning syncope can be the
        # last event before fatal ventricular fibrillation.
        "symptoms": ["dizziness", "palpitations"],
        "additional_indicators": [
            "blacked out", "passed out", "fainted", "lost consciousness", "collapsed",
            "fell to the ground", "went down", "dropped to the floor",
            "no warning", "without warning", "came out of nowhere", "suddenly collapsed",
            "during exercise", "while working out", "while running", "when i was exercising",
            "heart racing before", "heart was going crazy before", "heart was pounding before",
            "irregular heartbeat", "heart skipping", "known heart condition",
        ],
        "severity": "critical",
        "action": "Advise calling 911 or going to ER immediately. Cardiac syncope can precede life-threatening arrhythmia.",
    },
    {
        "id": "rf_acute_hf_decompensation",
        "name": "Acute heart failure decompensation",
        # Escalated to critical: acute pulmonary oedema can be fatal within
        # minutes to hours without IV diuresis.
        "symptoms": ["shortness_of_breath", "swelling"],
        "additional_indicators": [
            "can't lie flat", "can't lie down", "have to sleep sitting up", "sleeping in a chair",
            "propped up on pillows", "need extra pillows to breathe",
            "woke up gasping", "woke up not being able to breathe", "woke up struggling to breathe",
            "waking up short of breath", "woke up fighting for air",
            "gained a lot of weight", "gained weight really fast", "weight went up quickly",
            "both legs swollen", "both ankles swollen", "legs are really swollen",
            "shoes don't fit", "socks leaving marks", "ankles look puffy",
            "heart failure", "congestive heart failure", "chf", "known heart failure",
        ],
        "severity": "critical",
        "action": "Advise calling 911 or going to ER immediately. Risk of acute pulmonary oedema.",
    },
    {
        "id": "rf_severe_asthma",
        "name": "Severe asthma exacerbation",
        # Escalated to critical: status asthmaticus is life-threatening.
        # Action already advised 911 — severity now reflects that.
        "symptoms": ["shortness_of_breath", "cough"],
        "additional_indicators": [
            "can't finish a sentence", "can't complete a sentence", "can only say one word",
            "too breathless to talk", "can't speak", "speaking in single words",
            "inhaler isn't working", "inhaler not helping", "puffer not working",
            "used my inhaler but it's not working", "rescue inhaler not helping",
            "lips are blue", "lips going blue", "lips turning blue", "lips look blue",
            "fingernails going blue", "fingernails turning blue", "fingertips going blue",
            "skin going blue", "turning blue", "face going blue",
            "skin looks gray", "skin going gray", "looking gray",
            "leaning forward to breathe", "hunched over to breathe",
            "breathing has gone silent", "can't hear breathing anymore",
            "worst asthma attack", "never been this bad",
        ],
        "severity": "critical",
        "action": "Advise calling 911 immediately. Severe asthma can be fatal without emergency treatment.",
    },

    # -----------------------------------------------------------------------
    # HIGH — same-day evaluation required
    # -----------------------------------------------------------------------
    {
        "id": "rf_appendicitis",
        "name": "Possible appendicitis",
        "symptoms": ["abdominal_pain", "fever"],
        "additional_indicators": [
            "pain on the right side", "pain in my lower right", "right lower abdomen",
            "pain gets worse when i let go", "hurts more when pressure is released",
            "not hungry", "lost my appetite", "can't eat",
            "nausea", "feel sick", "vomiting",
        ],
        "severity": "high",
        "action": "Recommend same-day urgent evaluation.",
    },
    {
        "id": "rf_dvt",
        "name": "Possible deep vein thrombosis",
        "symptoms": ["swelling"],
        "additional_indicators": [
            "one leg swollen", "one leg bigger than the other", "one ankle swollen",
            "calf hurts", "calf is sore", "calf cramp that won't go away",
            "leg is warm", "leg feels hot", "leg is red",
            "just got off a long flight", "been in bed for a while", "just had an operation",
            "recently immobile", "haven't been moving much",
        ],
        "severity": "high",
        "action": "Recommend same-day evaluation. Advise against massaging the area.",
    },
    {
        "id": "rf_diabetic_foot_vascular",
        "name": "Foot pain in diabetic patient — possible peripheral vascular involvement",
        # Foot pain in a patient with diabetes raises the possibility of peripheral
        # arterial disease or neuropathic ulceration, both of which require prompt
        # evaluation to prevent limb-threatening complications.
        "symptoms": ["foot_pain"],
        "additional_indicators": [
            "diabetes", "diabetic", "type 2 diabetes", "type 1 diabetes",
            "blood sugar", "high blood sugar", "insulin", "metformin",
            "glucophage", "a1c", "hba1c",
            # Also fire if the patient's chronic conditions context string is injected
            "essential hypertension",  # commonly co-occurs with T2DM
        ],
        "severity": "high",
        "action": (
            "Recommend prompt evaluation. Foot pain in a diabetic patient may indicate "
            "peripheral arterial disease or neuropathic complications — both require "
            "early assessment to prevent ulceration or limb loss. Consider 45-minute slot."
        ),
    },
    {
        "id": "rf_retinal_detachment",
        "name": "Possible retinal detachment",
        "symptoms": ["vision_changes"],
        "additional_indicators": [
            "seeing floaters", "new floaters", "lots of floaters suddenly",
            "flashing lights", "seeing flashes",
            "curtain across my vision", "shadow in my vision", "like a curtain came down",
            "veil over my vision", "part of vision gone dark",
            "suddenly lost vision", "vision went dark", "vision cut out",
        ],
        "severity": "high",
        "action": "Recommend same-day ophthalmologic evaluation.",
    },
]


# ---------------------------------------------------------------------------
# PHQ-2 SCREENING QUESTIONS
# ---------------------------------------------------------------------------
# The Patient Health Questionnaire-2 is a validated depression screening tool.
# Scores >= 3 warrant a full PHQ-9 follow-up.
# ---------------------------------------------------------------------------

PHQ2_QUESTIONS: list[dict] = [
    {
        "id": "phq2_q1",
        "text": (
            "Over the last 2 weeks, how often have you been bothered by "
            "having little interest or pleasure in doing things?"
        ),
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
    {
        "id": "phq2_q2",
        "text": (
            "Over the last 2 weeks, how often have you been bothered by "
            "feeling down, depressed, or hopeless?"
        ),
        "options": [
            {"value": 0, "label": "Not at all"},
            {"value": 1, "label": "Several days"},
            {"value": 2, "label": "More than half the days"},
            {"value": 3, "label": "Nearly every day"},
        ],
    },
]


# ---------------------------------------------------------------------------
# YEARLY CHECKUP QUESTIONS
# ---------------------------------------------------------------------------
# Standard pre-visit questionnaire sent before annual wellness exams.
# Organized by category for the intake workflow.
# ---------------------------------------------------------------------------

YEARLY_CHECKUP_QUESTIONS: list[dict] = [
    # PHQ-2 screening
    {
        "id": "yc_phq2_q1",
        "category": "mental_health_screening",
        "text": PHQ2_QUESTIONS[0]["text"],
        "question_type": "scale",
        "options": PHQ2_QUESTIONS[0]["options"],
    },
    {
        "id": "yc_phq2_q2",
        "category": "mental_health_screening",
        "text": PHQ2_QUESTIONS[1]["text"],
        "question_type": "scale",
        "options": PHQ2_QUESTIONS[1]["options"],
    },
    # Medication reconciliation
    {
        "id": "yc_med_current",
        "category": "medication_reconciliation",
        "text": "Please list all medications you are currently taking, including over-the-counter medications and supplements.",
        "question_type": "short_answer",
    },
    {
        "id": "yc_med_changes",
        "category": "medication_reconciliation",
        "text": "Have any of your medications changed since your last visit?",
        "question_type": "yes_no",
    },
    {
        "id": "yc_med_side_effects",
        "category": "medication_reconciliation",
        "text": "Are you experiencing any side effects from your current medications?",
        "question_type": "yes_no",
    },
    {
        "id": "yc_med_adherence",
        "category": "medication_reconciliation",
        "text": "Are you taking all medications as prescribed?",
        "question_type": "yes_no",
    },
    # Vital signs / recent measurements
    {
        "id": "yc_bp_home",
        "category": "vital_signs",
        "text": "If you monitor your blood pressure at home, what are your recent readings?",
        "question_type": "short_answer",
    },
    {
        "id": "yc_weight_change",
        "category": "vital_signs",
        "text": "Have you had any significant weight changes in the past year?",
        "question_type": "yes_no",
    },
    # Lifestyle
    {
        "id": "yc_exercise",
        "category": "lifestyle",
        "text": "How many days per week do you engage in physical activity for at least 30 minutes?",
        "question_type": "short_answer",
    },
    {
        "id": "yc_tobacco",
        "category": "lifestyle",
        "text": "Do you currently use tobacco or nicotine products?",
        "question_type": "yes_no",
    },
    {
        "id": "yc_alcohol",
        "category": "lifestyle",
        "text": "How many alcoholic drinks do you have in a typical week?",
        "question_type": "short_answer",
    },
    {
        "id": "yc_sleep",
        "category": "lifestyle",
        "text": "On average, how many hours of sleep do you get per night?",
        "question_type": "short_answer",
    },
    {
        "id": "yc_diet",
        "category": "lifestyle",
        "text": "How would you rate your overall diet?",
        "question_type": "short_answer",
    },
    # Preventive care
    {
        "id": "yc_vaccines",
        "category": "preventive_care",
        "text": "Are you up to date on your vaccinations, including flu and COVID boosters?",
        "question_type": "yes_no",
    },
    {
        "id": "yc_screenings",
        "category": "preventive_care",
        "text": "Are there any recommended health screenings you have not completed (e.g., colonoscopy, mammogram)?",
        "question_type": "yes_no",
    },
    # General
    {
        "id": "yc_concerns",
        "category": "general",
        "text": "Do you have any specific health concerns you would like to discuss during your visit?",
        "question_type": "short_answer",
    },
    {
        "id": "yc_family_history",
        "category": "general",
        "text": "Have there been any new health conditions diagnosed in your immediate family since your last visit?",
        "question_type": "yes_no",
    },
]


# ---------------------------------------------------------------------------
# MEDICATION INTERACTION FLAGS
# ---------------------------------------------------------------------------
# Common clinically significant drug interactions that the system should flag.
# Each entry is a pair of drug classes / specific drugs plus the interaction
# concern.  This is NOT exhaustive -- it covers high-frequency primary care
# scenarios.
# ---------------------------------------------------------------------------

MEDICATION_INTERACTION_FLAGS: list[dict] = [
    {
        "drugs": ["warfarin", "nsaid"],
        "severity": "high",
        "description": "NSAIDs increase bleeding risk when combined with warfarin.",
        "recommendation": "Avoid concurrent use. Consider acetaminophen for pain.",
    },
    {
        "drugs": ["warfarin", "aspirin"],
        "severity": "high",
        "description": "Aspirin increases bleeding risk when combined with warfarin.",
        "recommendation": "Use only if specifically prescribed together. Monitor INR closely.",
    },
    {
        "drugs": ["ace_inhibitor", "potassium_supplement"],
        "severity": "moderate",
        "description": "ACE inhibitors can increase potassium levels; supplementation may cause hyperkalemia.",
        "recommendation": "Monitor serum potassium levels regularly.",
    },
    {
        "drugs": ["ace_inhibitor", "spironolactone"],
        "severity": "high",
        "description": "Both increase potassium levels, risk of life-threatening hyperkalemia.",
        "recommendation": "Close monitoring of potassium required. Consider alternatives.",
    },
    {
        "drugs": ["ssri", "maoi"],
        "severity": "critical",
        "description": "Combination can cause serotonin syndrome, a potentially fatal condition.",
        "recommendation": "Absolutely contraindicated. Requires 14-day washout between agents.",
    },
    {
        "drugs": ["ssri", "tramadol"],
        "severity": "high",
        "description": "Increased risk of serotonin syndrome and seizures.",
        "recommendation": "Avoid if possible. Monitor closely if no alternative.",
    },
    {
        "drugs": ["statin", "fibrate"],
        "severity": "moderate",
        "description": "Increased risk of rhabdomyolysis (muscle breakdown).",
        "recommendation": "Monitor for muscle pain/weakness. Check CK levels if symptomatic.",
    },
    {
        "drugs": ["metformin", "contrast_dye"],
        "severity": "high",
        "description": "Risk of lactic acidosis. Metformin should be held before contrast procedures.",
        "recommendation": "Hold metformin 48 hours before and after contrast administration.",
    },
    {
        "drugs": ["beta_blocker", "calcium_channel_blocker"],
        "severity": "moderate",
        "description": "Both slow heart rate; combination may cause severe bradycardia.",
        "recommendation": "Monitor heart rate closely. Avoid verapamil/diltiazem with beta-blockers.",
    },
    {
        "drugs": ["opioid", "benzodiazepine"],
        "severity": "critical",
        "description": "Combined CNS depression can cause fatal respiratory depression.",
        "recommendation": "Avoid concurrent use. FDA black box warning.",
    },
    {
        "drugs": ["lithium", "nsaid"],
        "severity": "high",
        "description": "NSAIDs reduce lithium clearance, increasing risk of toxicity.",
        "recommendation": "Monitor lithium levels closely. Use acetaminophen instead.",
    },
    {
        "drugs": ["digoxin", "amiodarone"],
        "severity": "high",
        "description": "Amiodarone increases digoxin levels, risk of toxicity.",
        "recommendation": "Reduce digoxin dose by 50% when starting amiodarone. Monitor levels.",
    },
    {
        "drugs": ["methotrexate", "trimethoprim"],
        "severity": "high",
        "description": "Trimethoprim increases methotrexate levels and toxicity risk.",
        "recommendation": "Avoid combination. Use alternative antibiotics.",
    },
    {
        "drugs": ["clopidogrel", "omeprazole"],
        "severity": "moderate",
        "description": "Omeprazole may reduce the antiplatelet effect of clopidogrel.",
        "recommendation": "Use pantoprazole instead if PPI needed.",
    },
    {
        "drugs": ["fluoroquinolone", "antacid"],
        "severity": "moderate",
        "description": "Antacids reduce absorption of fluoroquinolone antibiotics.",
        "recommendation": "Separate doses by at least 2 hours.",
    },
    {
        "drugs": ["thyroid_hormone", "calcium_supplement"],
        "severity": "moderate",
        "description": "Calcium reduces absorption of levothyroxine.",
        "recommendation": "Separate doses by at least 4 hours.",
    },
]
