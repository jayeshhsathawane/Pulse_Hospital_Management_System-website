from .models import VisitorCount

def visitor_count_processor(request):
    v_count, created = VisitorCount.objects.get_or_create(id=1)
    
    # Session ka use karein taki ek hi user bar-bar refresh karke count na badhaye
    if not request.session.get('has_visited'):
        v_count.counter += 1
        v_count.save()
        request.session['has_visited'] = True
        
    return {'total_visitors': v_count.counter}