import React from 'react';
import { ShieldCheck, Clock } from 'lucide-react';

export const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

export const parseCleanDate = (dateStr, isEnd = false) => {
  if (!dateStr) return null;
  let str = String(dateStr).trim();
  if (str.includes(' ')) str = str.split(' ')[0];
  if (str.includes('T')) str = str.split('T')[0];

  if (str.includes('/')) {
    const parts = str.split('/');
    if (parts.length === 3) {
      const day = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const year = parseInt(parts[2], 10);
      if (!isNaN(day) && !isNaN(month) && !isNaN(year)) {
        return isEnd
          ? new Date(year, month, day, 23, 59, 59)
          : new Date(year, month, day, 0, 0, 0);
      }
    }
  }

  if (str.includes('-')) {
    const parts = str.split('-');
    if (parts.length === 3) {
      let year, month, day;
      if (parts[0].length === 4) {
        year = parseInt(parts[0], 10);
        month = parseInt(parts[1], 10) - 1;
        day = parseInt(parts[2], 10);
      } else {
        day = parseInt(parts[0], 10);
        month = parseInt(parts[1], 10) - 1;
        year = parseInt(parts[2], 10);
      }
      if (!isNaN(day) && !isNaN(month) && !isNaN(year)) {
        return isEnd
          ? new Date(year, month, day, 23, 59, 59)
          : new Date(year, month, day, 0, 0, 0);
      }
    }
  }

  const d = new Date(str);
  return isNaN(d.getTime()) ? null : d;
};

export const formatPeriodBoundary = (dateStr) => {
  if (!dateStr) return '';
  const cleanStr = String(dateStr).trim();
  const parts = cleanStr.includes('T') ? cleanStr.split('T') : cleanStr.split(' ');
  const datePart = parts[0];
  const timePart = parts.length > 1 ? parts[1].split('.')[0] : '';
  const dSub = datePart.split('-');
  const formattedDate = dSub.length === 3 ? `${dSub[2]}/${dSub[1]}/${dSub[0]}` : datePart;

  if (timePart && timePart !== '00:00:00' && timePart !== '23:59:59' && timePart !== '00:00' && timePart !== '23:59') {
    const fullTime = timePart.length === 5 ? `${timePart}:00` : timePart.slice(0, 8);
    return `${formattedDate} ${fullTime}`;
  }
  return formattedDate;
};

export const formatPeriodRange = (startStr, endStr) => {
  if (!startStr && !endStr) return '';
  if (!startStr) return formatPeriodBoundary(endStr);
  if (!endStr) return formatPeriodBoundary(startStr);
  return `${formatPeriodBoundary(startStr)} al ${formatPeriodBoundary(endStr)}`;
};

export const formatDateTime = (dateStr, fallbackStr) => {
  if (!dateStr && !fallbackStr) return '';
  const targetStr = dateStr || fallbackStr;
  if (!targetStr) return '';
  const cleanStr = String(targetStr).trim();
  const parts = cleanStr.includes('T') ? cleanStr.split('T') : cleanStr.split(' ');
  const datePart = parts[0];
  let timePart = parts.length > 1 ? parts[1] : '';

  if (!timePart && fallbackStr) {
    const fbClean = String(fallbackStr).trim();
    const fbParts = fbClean.includes('T') ? fbClean.split('T') : fbClean.split(' ');
    if (fbParts.length > 1) {
      timePart = fbParts[1];
    }
  }

  const dSub = datePart.split('-');
  if (dSub.length === 3) {
    const formattedDate = `${dSub[2]}/${dSub[1]}/${dSub[0]}`;
    if (timePart && timePart !== '00:00:00' && timePart !== '23:59:59') {
      const cleanTime = timePart.split('.')[0];
      const fullTime = cleanTime.length === 5 ? `${cleanTime}:00` : cleanTime.slice(0, 8);
      return `${formattedDate} ${fullTime}`;
    }
    return formattedDate;
  }
  return targetStr;
};

export const formatDateDisplay = (dateStr, fallbackStr) => {
  if (!dateStr && !fallbackStr) return '';
  const targetStr = dateStr || fallbackStr;
  if (!targetStr) return '';
  const cleanStr = String(targetStr).trim();
  const parts = cleanStr.includes('T') ? cleanStr.split('T') : cleanStr.split(' ');
  const datePart = parts[0];
  const timePart = parts.length > 1 ? parts[1].split('.')[0] : '';

  const dSub = datePart.split('-');
  if (dSub.length === 3) {
    const formattedDate = `${dSub[2]}/${dSub[1]}/${dSub[0]}`;
    if (timePart && timePart !== '00:00:00' && timePart !== '00:00') {
      const fullTime = timePart.length === 5 ? `${timePart}:00` : timePart.slice(0, 8);
      return `${formattedDate} ${fullTime}`;
    }
    return formattedDate;
  }
  return targetStr;
};

export const renderIssueDateBadge = (dateStr, fallbackStr) => {
  if (!dateStr && !fallbackStr) return <span style={{ color: 'var(--text-muted)' }}>-</span>;
  const targetStr = dateStr || fallbackStr;
  if (!targetStr) return <span style={{ color: 'var(--text-muted)' }}>-</span>;
  const cleanStr = String(targetStr).trim();
  const parts = cleanStr.includes('T') ? cleanStr.split('T') : cleanStr.split(' ');
  const datePart = parts[0];
  const timePart = parts.length > 1 ? parts[1].split('.')[0] : '';

  let formattedDate = cleanStr;
  const dSub = datePart.split('-');
  if (dSub.length === 3) {
    formattedDate = `${dSub[2]}/${dSub[1]}/${dSub[0]}`;
  }

  const hasExplicitTime = Boolean(timePart && timePart !== '00:00:00' && timePart !== '00:00');

  if (hasExplicitTime) {
    const fullTime = timePart.length === 5 ? `${timePart}:00` : timePart.slice(0, 8);
    const fullDisplay = `${formattedDate} ${fullTime}`;
    return (
      <div
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
        title="Firma digital con estampado de tiempo oficial CPCE."
      >
        <span style={{ fontWeight: 500 }}>{fullDisplay}</span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '0.12rem 0.4rem',
            borderRadius: '4px',
            background: 'rgba(16, 185, 129, 0.12)',
            color: '#34D399',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            fontSize: '0.68rem',
            fontWeight: 600,
            cursor: 'help'
          }}
          title="Firma digital con estampado de tiempo oficial CPCE."
        >
          <ShieldCheck size={11} style={{ marginRight: '0.2rem' }} /> CPCE TS
        </span>
      </div>
    );
  } else {
    return (
      <div
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
        title="La oblea se emitió sin timestamp de horas/minutos/segundos (sólo día oficial)."
      >
        <span style={{ fontWeight: 500 }}>{formattedDate}</span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '0.12rem 0.4rem',
            borderRadius: '4px',
            background: 'rgba(234, 179, 8, 0.12)',
            color: '#FBBF24',
            border: '1px solid rgba(234, 179, 8, 0.3)',
            fontSize: '0.68rem',
            fontWeight: 600,
            cursor: 'help'
          }}
          title="La oblea se emitió sin timestamp de horas/minutos/segundos (sólo día oficial)."
        >
          <Clock size={10} style={{ marginRight: '0.2rem' }} /> Día oficial
        </span>
      </div>
    );
  }
};

export const CERT_COLORS = [
  { border: '#4F46E5', bg: 'rgba(79, 70, 229, 0.18)', text: '#818CF8', lightBg: 'rgba(79, 70, 229, 0.08)' },
  { border: '#10B981', bg: 'rgba(16, 185, 129, 0.18)', text: '#34D399', lightBg: 'rgba(16, 185, 129, 0.08)' },
  { border: '#06B6D4', bg: 'rgba(6, 182, 212, 0.18)', text: '#38BDF8', lightBg: 'rgba(6, 182, 212, 0.08)' },
  { border: '#8B5CF6', bg: 'rgba(139, 92, 246, 0.18)', text: '#C084FC', lightBg: 'rgba(139, 92, 246, 0.08)' },
  { border: '#F59E0B', bg: 'rgba(245, 158, 11, 0.18)', text: '#FBBF24', lightBg: 'rgba(245, 158, 11, 0.08)' }
];

export const getCertColor = (cert, certificationsList = []) => {
  if (!cert) return CERT_COLORS[0];
  const idx = certificationsList.findIndex((c) => c === cert || (c && cert && c.id === cert.id));
  const safeIdx = idx >= 0 ? idx : 0;
  return CERT_COLORS[safeIdx % CERT_COLORS.length] || CERT_COLORS[0];
};

export const getCertsForMonth = (monthIndex, selectedYear, certificationsList = []) => {
  const startOfMonth = new Date(selectedYear, monthIndex, 1, 0, 0, 0);
  const endOfMonth = new Date(selectedYear, monthIndex + 1, 0, 23, 59, 59);

  return certificationsList.filter((cert) => {
    if (!cert) return false;
    const cStart = parseCleanDate(cert.start_date);
    const cEnd = parseCleanDate(cert.end_date, true);
    if (!cStart || !cEnd) return false;
    return cStart <= endOfMonth && cEnd >= startOfMonth;
  });
};

export const getMonthCertInfo = (monthIndex, selectedYear, certificationsList = []) => {
  const monthCerts = getCertsForMonth(monthIndex, selectedYear, certificationsList);
  const totalDays = new Date(selectedYear, monthIndex + 1, 0).getDate();
  if (monthCerts.length === 0) return { status: 'none', certs: [], coveredDays: 0, totalDays };

  let coveredDays = 0;
  for (let d = 1; d <= totalDays; d++) {
    const dayStart = new Date(selectedYear, monthIndex, d, 0, 0, 0);
    const dayEnd = new Date(selectedYear, monthIndex, d, 23, 59, 59);
    const isCovered = monthCerts.some((cert) => {
      const cStart = parseCleanDate(cert.start_date);
      const cEnd = parseCleanDate(cert.end_date, true);
      return cStart && cEnd && cStart <= dayEnd && cEnd >= dayStart;
    });
    if (isCovered) coveredDays++;
  }
  const status = coveredDays >= totalDays ? 'full' : coveredDays > 0 ? 'partial' : 'none';
  return { status, certs: monthCerts, coveredDays, totalDays };
};

export const getMonthCoverageStatus = (monthIndex, selectedYear, certificationsList = []) => {
  const certInfo = getMonthCertInfo(monthIndex, selectedYear, certificationsList);
  const startOfMonth = new Date(selectedYear, monthIndex, 1);
  const today = new Date();

  if (certInfo.status === 'full') return 'certified';
  if (certInfo.status === 'partial') return 'partial';
  if (startOfMonth > today) return 'future';
  return 'pending';
};

export const assignBarLanes = (bars = []) => {
  const lanes = [];
  bars.forEach((bar) => {
    let placed = false;
    for (let r = 0; r < lanes.length; r++) {
      const lastInLane = lanes[r][lanes[r].length - 1];
      if (String(lastInLane.end_date).slice(0, 10) < String(bar.start_date).slice(0, 10)) {
        let adjStart = bar.startMonth;
        if (lastInLane.endMonth >= adjStart) {
          if (bar.endMonth > lastInLane.endMonth) {
            adjStart = lastInLane.endMonth + 1;
          } else {
            continue;
          }
        }
        if (adjStart <= bar.endMonth) {
          bar.startMonth = adjStart;
          bar.rowIndex = r;
          lanes[r].push(bar);
          placed = true;
          break;
        }
      }
    }
    if (!placed) {
      bar.rowIndex = lanes.length;
      lanes.push([bar]);
    }
  });
  return bars;
};

export const getYearCertificationBrackets = (selectedYear, certificationsList = []) => {
  const yearStart = new Date(selectedYear, 0, 1, 0, 0, 0);
  const yearEnd = new Date(selectedYear, 11, 31, 23, 59, 59);

  const rawList = certificationsList
    .map((cert) => {
      if (!cert) return null;
      const cStart = parseCleanDate(cert.start_date);
      const cEnd = parseCleanDate(cert.end_date, true);
      if (!cStart || !cEnd) return null;
      if (cStart > yearEnd || cEnd < yearStart) return null;

      const startMonth = cStart < yearStart ? 0 : cStart.getMonth();
      const endMonth = cEnd > yearEnd ? 11 : cEnd.getMonth();
      const colorScheme = getCertColor(cert, certificationsList);

      return {
        cert,
        start_date: cert.start_date,
        end_date: cert.end_date,
        startMonth,
        endMonth,
        colorScheme,
        cStart,
        cEnd
      };
    })
    .filter(Boolean);

  rawList.sort((a, b) => a.cStart - b.cStart);
  return assignBarLanes(rawList);
};
