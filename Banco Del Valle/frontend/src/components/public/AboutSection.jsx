import React from 'react';
import { ShieldCheck, Landmark, Users } from 'lucide-react';

/**
 * AboutSection — Respaldo institucional y origen en el Valle de Catamarca (Alto contraste y Dark Mode).
 */
export function AboutSection() {
  const pilares = [
    {
      icon: Landmark,
      titulo: 'Solidez Institucional',
      desc: 'Cumplimiento estricto del régimen de Efectivo Mínimo del BCRA y reserva fraccionaria prudencial.',
    },
    {
      icon: Users,
      titulo: 'Cercanía y Empatía Regional',
      desc: 'Nacidos en el Valle central para conectar a familias catamarqueñas con bienes reales y progreso.',
    },
    {
      icon: ShieldCheck,
      titulo: 'Transparencia Financiera',
      desc: 'Tasas competitivas transparentes y evaluación crediticia objetiva basada en tu capacidad real de repago.',
    },
  ];

  return (
    <section id="nosotros" className="my-16">
      <div className="text-center max-w-2xl mx-auto mb-12">
        <span className="text-xs sm:text-sm font-bold uppercase tracking-wider text-valle-orange">
          Identidad y Compromiso Regional
        </span>
        <h2 className="font-display font-extrabold text-2xl sm:text-4xl text-slate-900 dark:text-white mt-1">
          Nuestra Huella en Catamarca
        </h2>
        <p className="text-slate-600 dark:text-slate-300 text-sm sm:text-base mt-2 leading-relaxed">
          Combinamos la calidez y el arraigo del sol norteño con tecnología financiera cuantitativa
          para ofrecer una banca accesible, moderna y honesta.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {pilares.map((p, idx) => {
          const Icon = p.icon;
          return (
            <div key={idx} className="valle-card rounded-3xl p-7 sm:p-8 flex flex-col justify-between transition-colors">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-valle-blue/10 dark:bg-valle-darkElevated border border-valle-blue/20 dark:border-valle-darkBorder text-valle-orange flex items-center justify-center mb-5">
                  <Icon className="w-6 h-6" />
                </div>
                <h3 className="font-display font-extrabold text-lg sm:text-xl text-slate-900 dark:text-white mb-2.5">
                  {p.titulo}
                </h3>
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-normal">
                  {p.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default AboutSection;
