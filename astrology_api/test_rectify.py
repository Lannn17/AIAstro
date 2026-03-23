import traceback, json
try:
    from app.rag import analyze_rectification
    top3 = [{'hour': 14, 'minute': 32, 'score': 8.5, 'asc_sign': 'Libra'}]
    events = [{'year': 2020, 'month': 6, 'day': 1, 'event_type': 'marriage', 'weight': 2}]
    result = analyze_rectification({}, top3, events)
    print('keys:', list(result.keys()))
    print('candidates:', result.get('candidates'))
    print('overall:', result.get('overall', '')[:300])
except Exception as e:
    traceback.print_exc()
