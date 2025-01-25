import numpy as np
import pickle
from functools import lru_cache
import re

def _clean_text(text: str) -> str:
    text = re.sub(r'[^a-zA-Zа-яА-ЯіІїЇєЄґҐ\s]', ' ', text.lower())
    return ' '.join(text.split())


def cosine_similarity_numpy(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    Вычисляет косинусное сходство между двумя векторами используя numpy.
    
    Args:
        v1, v2: numpy массивы любой формы
        
    Returns:
        float: Косинусное сходство в диапазоне [-1, 1]
    """
    v1 = np.asarray(v1, dtype=np.float64)
    v2 = np.asarray(v2, dtype=np.float64)
    
    v1_flat = v1.reshape(-1)
    v2_flat = v2.reshape(-1)
    
    if len(v1_flat) != len(v2_flat):
        raise ValueError(f"Vectors must have the same length, got {len(v1_flat)} and {len(v2_flat)}")
    
    eps = 1e-8
    
    dot_product = np.dot(v1_flat, v2_flat)
    norm_v1 = np.linalg.norm(v1_flat)
    norm_v2 = np.linalg.norm(v2_flat)
    
    if norm_v1 < eps or norm_v2 < eps:
        return 0.0
        
    return float(dot_product / (norm_v1 * norm_v2))

@lru_cache(maxsize=1)
def _get_cached_model():
    try:
        with open('./app/data/toxic_detector_improved_03.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        raise Exception("Model file not found. Please run training first.")
    

def is_toxic_message(text: str, threshold_adjust: float = 0.0) -> tuple[bool, float, str]:
    if not text: return (False, 0.0, "")
    data = _get_cached_model()
    model = data['model']
    toxic_embeddings = data['toxic_embeddings']
    base_threshold = data['threshold']
    threshold = max(0.1, min(0.95, base_threshold + threshold_adjust))
    
    text = _clean_text(text)
    words = text.split()

    max_similarity = 0.0
    toxic_match = ""
    
    for word in words:
        if word in model.wv:
            word_vector = model.wv[word]
            
            for toxic_word, toxic_vector in toxic_embeddings.items():
                try:
                    similarity = cosine_similarity_numpy(word_vector, toxic_vector)
                    # print((toxic_word, word, similarity))
                    # similarity = np.dot(word_vector, toxic_vector) / (
                    #     np.linalg.norm(word_vector) * np.linalg.norm(toxic_vector)
                    # )
                    
                    if similarity > max_similarity:
                        max_similarity = similarity
                        toxic_match = toxic_word
                    
                    if similarity > threshold:

                        return True, similarity, toxic_word
                        
                except Exception as e:
                    print(f"Error processing word '{word}': {str(e)}")
                    continue

    return False, max_similarity, toxic_match