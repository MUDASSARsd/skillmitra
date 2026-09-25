import json
from backend.database.db import init_db
from backend.courses.store import import_skill_india_json, course_data_status, search_courses, courses_for_qualification


def payload():
    return {
      'IsSuccess': True,
      'Data': {
        'Pagination': {'CurrentPageNumber':1,'CurrentPageSize':2,'TotalCount':1581},
        'Courses': [
          {
            'Id':'c1','Code':'course-v1:test+1','ReadableCode':'R1','Title':'Personal Trainer (B&W)',
            'CourseInformation':{'NsqfLevel':4,'QpCode':[{'QpCode':'BWS/Q3003'}],'NosCode':[{'Noscode':'BWS/N3003'}]},
            'CreatedBy':'Beauty & Wellness Sector Skill Council','CourseProviderId':'p1','Programs':[{'Program':'NSDC Academy'}],
            'InitiativeOfs':[{'Initiative':'NSDC Academy'}],'Language':'Hindi','Price':0,'CourseMode':1,'Availability':1,
            'Occupations':[{'Occupation':'Fitness Services'}],'Domains':[{'Domain':'Fitness'}],
            'ShortDescription':'Fitness assessment and personalized training programmes.',
            'CourseStatistic':{'EnrollmentCount':998,'RatingAverage':4.4},
            'CourseCriteria':[{'Name':'age_requirement','Value':'Above 20'},{'Name':'educational_qualification','Value':'10th Pass'},{'Name':'industry_experience','Value':'2-3'}]
          },
          {
            'Id':'c2','Code':'course-v1:test+2','Title':'Electrician Second Year','CourseInformation':{'NsqfLevel':4.5,'QpCode':[],'NosCode':[]},
            'CreatedBy':'NIMI','Language':'English','CourseMode':1,'Availability':1,
            'Occupations':[{'Occupation':'Technician'}],'Domains':[{'Domain':'Distribution'}],
            'ShortDescription':'Electrician course parallel learning material.'
          }
        ]
      }
    }


def test_course_import_and_search(tmp_path):
    db=tmp_path/'test.db'; init_db(db).close()
    p=tmp_path/'courses.json'; p.write_text(json.dumps(payload()),encoding='utf-8')
    r=import_skill_india_json(p,db)
    assert r['courses_upserted']==2
    st=course_data_status(db)
    assert st['cached_courses']==2 and st['availability_flagged_courses']==2
    m=search_courses('personal trainer',db_path=db)
    assert m and m[0].course.course_id=='c1'
    assert m[0].course.educational_qualification=='10th Pass'


def test_course_import_idempotent(tmp_path):
    db=tmp_path/'test.db'; init_db(db).close()
    p=tmp_path/'courses.json'; p.write_text(json.dumps(payload()),encoding='utf-8')
    import_skill_india_json(p,db); import_skill_india_json(p,db)
    assert course_data_status(db)['cached_courses']==2


def test_qualification_title_fallback(tmp_path):
    db=tmp_path/'test.db'; con=init_db(db)
    con.execute("INSERT INTO qualifications(s_no,title,code,proposed_occupation) VALUES (?,?,?,?)",(1,'Personal Trainer (B&W)','QG-TEST','Fitness Services'))
    con.commit(); con.close()
    p=tmp_path/'courses.json'; p.write_text(json.dumps(payload()),encoding='utf-8')
    import_skill_india_json(p,db)
    m=courses_for_qualification('QG-TEST',db_path=db)
    assert m and m[0].course.course_id=='c1'
    assert m[0].match_type in {'exact_title','title'}
