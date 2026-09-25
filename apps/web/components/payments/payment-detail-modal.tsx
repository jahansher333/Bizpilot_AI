"use client";

import React from "react";
import { formatMoney, Payment } from "@/lib/schemas/payments";

interface PaymentDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  payment: Payment | null;
}

export function PaymentDetailModal({
  isOpen,
  onClose,
  payment,
}: PaymentDetailModalProps) {
  if (!isOpen || !payment) return null;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800 border-green-200";
      case "voided":
        return "bg-red-100 text-red-800 border-red-200";
      case "corrected":
        return "bg-amber-100 text-amber-800 border-amber-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const formatChannel = (ch: string) => {
    switch (ch) {
      case "cash":
        return "Cash";
      case "bank_transfer":
        return "Bank Transfer";
      case "cheque":
        return "Cheque";
      case "mobile_wallet":
        return "Mobile Wallet";
      default:
        return ch;
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="payment-detail-modal-title"
    >
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between border-b pb-3">
          <div>
            <h2 id="payment-detail-modal-title" className="text-lg font-semibold text-gray-900">
              Receipt Details
            </h2>
            <p className="text-xs text-gray-500 font-mono">{payment.payment_number}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="mt-4 space-y-4 text-sm">
          {/* Status & Amount */}
          <div className="flex items-center justify-between rounded-lg bg-gray-50 p-3 border border-gray-100">
            <div>
              <span className="text-xs text-gray-500">Collected Amount</span>
              <p className="text-xl font-bold text-gray-900">
                {formatMoney(payment.amount_minor, payment.currency_code)}
              </p>
            </div>
            <span
              className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${getStatusBadge(
                payment.status
              )}`}
            >
              {payment.status}
            </span>
          </div>

          {/* Core Info Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-xs font-medium text-gray-500">Payment Channel</span>
              <p className="font-medium text-gray-900 capitalize">
                {formatChannel(payment.channel)}
              </p>
            </div>

            <div>
              <span className="text-xs font-medium text-gray-500">Account / Drawer</span>
              <p className="font-medium text-gray-900">
                {payment.account_label || "—"}
              </p>
            </div>

            <div>
              <span className="text-xs font-medium text-gray-500">Customer ID</span>
              <p className="font-mono text-xs text-gray-700 break-all">
                {payment.customer_id || "None (Walk-in)"}
              </p>
            </div>

            <div>
              <span className="text-xs font-medium text-gray-500">Order ID</span>
              <p className="font-mono text-xs text-gray-700 break-all">
                {payment.order_id || "None (Direct Receipt)"}
              </p>
            </div>

            <div>
              <span className="text-xs font-medium text-gray-500">External Reference</span>
              <p className="font-mono text-xs text-gray-700">
                {payment.external_reference || "—"}
              </p>
            </div>

            <div>
              <span className="text-xs font-medium text-gray-500">Received Date</span>
              <p className="text-gray-900 text-xs">
                {new Date(payment.received_at).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Replacement / Void Status Details */}
          {payment.status === "voided" && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-800">
              <span className="font-semibold">Voided Record:</span> This receipt was marked as void
              {payment.voided_at && ` on ${new Date(payment.voided_at).toLocaleString()}`} and is
              excluded from active financial totals.
            </div>
          )}

          {payment.status === "corrected" && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 space-y-1">
              <p className="font-semibold">Corrected Record:</p>
              <p>This payment was replaced by a corrective receipt.</p>
              {payment.replaced_by_payment_id && (
                <p className="font-mono">
                  Replacement ID: {payment.replaced_by_payment_id}
                </p>
              )}
            </div>
          )}

          {payment.corrects_payment_id && (
            <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800">
              <span className="font-semibold">Correction Trace:</span> This receipt replaced an earlier
              entry (Prior Payment ID: <span className="font-mono">{payment.corrects_payment_id}</span>).
            </div>
          )}

          {/* Notes */}
          {payment.notes && (
            <div>
              <span className="text-xs font-medium text-gray-500">Notes</span>
              <p className="mt-1 rounded bg-gray-50 p-2 text-xs text-gray-700 border border-gray-100">
                {payment.notes}
              </p>
            </div>
          )}

          {/* Audit Timestamp */}
          <div className="border-t pt-3 text-xs text-gray-400">
            Recorded at {new Date(payment.created_at).toLocaleString()}
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
