#!/usr/bin/env python3
"""Component-level source transfer and attention-path interventions."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from _paths import FIGURES
from style_main_figures import BLUE, TEAL, ORANGE, GRAY, save

fig,ax=plt.subplots(figsize=(7.1,3.45))
ax.set(xlim=(0,14),ylim=(0,6));ax.axis('off')
def text(x,y,s,size=8,color='#263746',**kw):
    ax.text(x,y,s,fontsize=size,color=color,va='center',**kw)
def box(x,y,w,h,label,color=GRAY,fill='#F5F8FA',size=8):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.04,rounding_size=.07',
                 facecolor=fill,edgecolor=color,linewidth=.7))
    text(x+w/2,y+h/2,label,size,color,ha='center',linespacing=1.4)
def arrow(x1,y1,x2,y2,color=GRAY):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',
                 mutation_scale=8,color=color,lw=.9))
def cut(x,y):
    ax.plot([x-.10,x+.10],[y-.12,y+.12],color=ORANGE,lw=1.3)
    ax.plot([x-.10,x+.10],[y+.12,y-.12],color=ORANGE,lw=1.3)

text(.1,5.8,'(a) Replace selected skill components at layer L',9.2,fontweight='bold')
text(1.6,5.28,'Correct-skill donor',8.2,ha='center',fontweight='bold')
text(6.5,5.28,'Wrong-skill receiver',8.2,ha='center',fontweight='bold')
box(.2,4.25,2.8,.60,'Skill-position states',BLUE)
box(.2,3.25,2.8,.60,'Skill-position KV cache\nlayers 0 through L',TEAL,size=7.6)
box(4.7,4.25,3.6,.60,'Replace skill states at L',BLUE)
box(4.7,3.25,3.6,.60,'Replace skill KV entries',TEAL)
arrow(3.08,4.55,4.6,4.55,BLUE);text(3.83,4.78,'S',7,BLUE,ha='center',fontweight='bold')
arrow(3.08,3.55,4.6,3.55,TEAL);text(3.83,3.85,'C',7,TEAL,ha='center',fontweight='bold')
text(6.5,2.89,'SC = both replacements',7.7,ha='center')
box(9.2,3.25,4.4,1.60,'Continue the receiver\n\nEarlier post-skill computation\nretained',GRAY,size=7.7)
arrow(8.4,4.55,9.1,4.55,BLUE);arrow(8.4,3.55,9.1,3.55,TEAL)
ax.plot([.1,13.8],[2.56,2.56],color='#D8E0E7',lw=.65)

text(.1,2.28,'(b) Test which attention access is needed afterward',9.2,fontweight='bold')
for x,title,top,bottom,start in [
    (.2,'All-query skill knockout','All query tokens','Skill keys','From L in the original run'),
    (4.9,'Post-skill-to-skill cut','Post-skill query tokens','Skill keys','From L+1 after SC, or L in donor'),
    (9.5,'Skill-to-skill cut','Skill query tokens','Skill keys','From L in the original run')]:
    text(x+1.9,1.84,title,7.8,ha='center',fontweight='bold')
    box(x,1.12,3.8,.42,top,size=7.6)
    box(x,.24,3.8,.42,bottom,TEAL,size=7.6)
    arrow(x+1.9,1.05,x+1.9,.73,TEAL);cut(x+1.9,.89)
    text(x+1.9,-.08,start,7.1,ha='center',color='#657889')
fig.subplots_adjust(left=.01,right=.99,top=.99,bottom=.08)
save(fig,'fig-intervention-design')
